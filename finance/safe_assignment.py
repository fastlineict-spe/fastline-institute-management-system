from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from students.models import Student
from .models import FeeAssignment, StudentFeeCharge


class SafeFeeAssignmentForm(forms.Form):
    assignment_type = forms.ChoiceField(choices=(("CLASS", "Programme / year group"), ("INDIVIDUAL", "Individual student")))
    campus = forms.ModelChoiceField(queryset=None)
    programme = forms.CharField(required=False, max_length=150)
    year_of_study = forms.IntegerField(required=False, min_value=1)
    student = forms.ModelChoiceField(queryset=None, required=False)
    academic_year = forms.CharField(max_length=30)
    semester = forms.CharField(max_length=30)
    amount = forms.DecimalField(min_value=Decimal("0.01"), max_digits=12, decimal_places=2)
    description = forms.CharField(max_length=200)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import Campus
        self.fields["campus"].queryset = Campus.objects.filter(is_active=True)
        self.fields["student"].queryset = Student.objects.filter(status=Student.Status.ACTIVE).order_by("user__first_name")
        profile = getattr(user, "profile", None)
        role = (getattr(profile, "role", "") or "").upper()
        central = user.is_superuser or role in ("SUPERADMIN", "CENTRAL_ADMIN")
        if not central:
            campus = getattr(profile, "campus", None)
            if campus is None:
                self.fields["campus"].queryset = Campus.objects.none()
                self.fields["student"].queryset = Student.objects.none()
            else:
                self.fields["campus"].queryset = Campus.objects.filter(pk=campus.pk, is_active=True)
                self.fields["student"].queryset = Student.objects.filter(campus=campus, status=Student.Status.ACTIVE)
        self.fields["campus"].widget.attrs["class"] = "form-control"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


def _can_manage_fees(user):
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and getattr(profile, "is_active", True) and
                (getattr(profile, "role", "").upper() in ("ADMINISTRATOR", "CENTRAL_ADMIN", "SUPERADMIN")))


def _central(user):
    profile = getattr(user, "profile", None)
    return user.is_superuser or bool(profile and getattr(profile, "role", "").upper() in ("CENTRAL_ADMIN", "SUPERADMIN"))


@login_required
def fee_assignment_preview(request):
    if not _can_manage_fees(request.user):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("finance:fee_assignment")
    form = SafeFeeAssignmentForm(request.POST, user=request.user)
    if not form.is_valid():
        return render(request, "finance/fee_assignment_preview.html", {"form": form, "errors": form.errors})
    data = form.cleaned_data
    campus = data["campus"]
    if not _central(request.user):
        profile = request.user.profile
        if not getattr(profile, "campus_id", None) or profile.campus_id != campus.pk:
            raise PermissionDenied
    if data["assignment_type"] == "INDIVIDUAL":
        student = data["student"]
        if not student or student.status != Student.Status.ACTIVE or student.campus_id != campus.pk:
            form.add_error("student", "Choose an active student from the selected campus.")
            return render(request, "finance/fee_assignment_preview.html", {"form": form})
        students = Student.objects.filter(pk=student.pk)
    else:
        if not data["programme"] or not data["year_of_study"]:
            form.add_error(None, "Programme and year of study are required for group assignment.")
            return render(request, "finance/fee_assignment_preview.html", {"form": form})
        students = Student.objects.filter(
            campus=campus, is_active=True,
            programme__iexact=data["programme"].strip(),
            year_of_study=data["year_of_study"]
        ).order_by("user__first_name", "user__last_name")
    # Exclude already charged students for the same campus/year/semester/description.
    existing_ids = set(StudentFeeCharge.objects.filter(
        campus=campus, academic_year=data["academic_year"],
        semester=data["semester"], description__iexact=data["description"].strip()
    ).values_list("student_id", flat=True))
    candidates = list(students)
    already_charged = [s for s in candidates if s.pk in existing_ids]
    candidates = [s for s in candidates if s.pk not in existing_ids]
    if not candidates:
        messages.warning(request, "No eligible students remain. They may already have this fee item.")
        return redirect("finance:fee_assignment")
    request.session["fims_fee_preview"] = {
        "student_ids": [s.pk for s in candidates],
        "campus_id": campus.pk,
        "assignment_type": data["assignment_type"],
        "programme": data["programme"],
        "year_of_study": data["year_of_study"],
        "academic_year": data["academic_year"],
        "semester": data["semester"],
        "amount": str(data["amount"]),
        "description": data["description"].strip(),
    }
    return render(request, "finance/fee_assignment_preview.html", {
        "students": candidates, "already_charged": already_charged,
        "data": data, "total": data["amount"] * len(candidates),
    })


@login_required
def fee_assignment_confirm(request):
    if not _can_manage_fees(request.user):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("finance:fee_assignment")
    payload = request.session.get("fims_fee_preview")
    if not payload:
        messages.error(request, "Preview expired. Please prepare the assignment again.")
        return redirect("finance:fee_assignment")
    from accounts.models import Campus
    campus = Campus.objects.get(pk=payload["campus_id"], is_active=True)
    if not _central(request.user):
        if getattr(request.user.profile, "campus_id", None) != campus.pk:
            raise PermissionDenied
    with transaction.atomic():
        allowed_ids = set(payload["student_ids"])
        try:
            selected_ids = {int(value) for value in request.POST.getlist("include_ids")}
        except (TypeError, ValueError):
            selected_ids = set()
        ids = list(allowed_ids.intersection(selected_ids))
        if not ids:
            messages.error(request, "Select at least one student before confirming.")
            return redirect("finance:fee_assignment")
        locked = list(Student.objects.select_for_update().filter(
            pk__in=ids, campus=campus, status=Student.Status.ACTIVE
        ))
        if len(locked) != len(ids):
            messages.error(request, "The student list changed after preview. Please preview again.")
            return redirect("finance:fee_assignment")
        duplicates = StudentFeeCharge.objects.filter(
            student_id__in=ids, campus=campus,
            academic_year=payload["academic_year"], semester=payload["semester"],
            description__iexact=payload["description"]
        ).exists()
        if duplicates:
            messages.error(request, "At least one student has already received this fee item. Nothing was saved; preview again.")
            return redirect("finance:fee_assignment")
        assignment = FeeAssignment.objects.create(
            campus=campus, assignment_type=payload["assignment_type"],
            programme=payload["programme"], year_of_study=payload["year_of_study"],
            student=locked[0] if payload["assignment_type"] == "INDIVIDUAL" else None,
            academic_year=payload["academic_year"], semester=payload["semester"],
            amount=Decimal(payload["amount"]), description=payload["description"],
            created_by=request.user, is_active=True
        )
        StudentFeeCharge.objects.bulk_create([
            StudentFeeCharge(
                assignment=assignment, student=s, campus=campus,
                academic_year=payload["academic_year"], semester=payload["semester"],
                description=payload["description"], amount=Decimal(payload["amount"])
            ) for s in locked
        ])
    del request.session["fims_fee_preview"]
    messages.success(request, f"Fee assigned to {len(locked)} student(s). Total assigned: UGX {Decimal(payload['amount']) * len(locked):,.0f}.")
    return redirect("finance:fee_assignment")

