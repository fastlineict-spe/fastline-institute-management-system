from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils import timezone
from accounts.models import Campus
from students.models import Student
from .forms import FeeAssignmentForm
from .models import FeeAssignment, StudentFeeCharge


def _allowed(user):
    return user.is_authenticated and user.is_active and (
        user.is_superuser or user.role == "ADMINISTRATOR"
    ) and (user.is_superuser or getattr(user, "is_central_admin", False) or user.campus_id)


@login_required
def fee_assignment(request):
    if not _allowed(request.user):
        raise PermissionDenied("Only authorised administrators can assign fees.")
    if request.method == "POST":
        form = FeeAssignmentForm(request.POST, user=request.user)
        if form.is_valid():
            data = form.cleaned_data
            campus = data["campus"]
            central = request.user.is_superuser or getattr(request.user, "is_central_admin", False)
            if not central and campus.pk != request.user.campus_id:
                raise PermissionDenied("You cannot assign fees for another campus.")

            assignment_type = data["assignment_type"]
            if assignment_type == FeeAssignment.AssignmentType.INDIVIDUAL:
                student = data.get("student")
                if not student or student.campus_id != campus.pk:
                    form.add_error("student", "Select an active student belonging to the selected campus.")
                else:
                    students = Student.objects.filter(pk=student.pk, status="ACTIVE")
            else:
                if not data.get("programme") or not data.get("year_of_study"):
                    form.add_error(None, "For class assignment, select a programme and year of study.")
                    students = Student.objects.none()
                else:
                    students = Student.objects.filter(
                        campus=campus, status="ACTIVE",
                        programme__iexact=data["programme"].strip(),
                        year_of_study=data["year_of_study"],
                    )

            if form.is_valid():
                if not students.exists():
                    form.add_error(None, "No active students match this assignment. No fees were assigned.")
                else:
                    with transaction.atomic():
                        assignment = FeeAssignment.objects.create(
                            campus=campus, assignment_type=assignment_type,
                            programme=data["programme"].strip() if assignment_type == "CLASS" else "",
                            year_of_study=data["year_of_study"] if assignment_type == "CLASS" else None,
                            student=data.get("student") if assignment_type == "INDIVIDUAL" else None,
                            academic_year=data["academic_year"].strip(),
                            semester=data["semester"], amount=data["amount"],
                            description=data["description"].strip(), created_by=request.user,
                        )
                        StudentFeeCharge.objects.bulk_create([
                            StudentFeeCharge(
                                assignment=assignment, student=student, campus=campus,
                                academic_year=assignment.academic_year,
                                semester=assignment.semester,
                                description=assignment.description, amount=assignment.amount,
                            ) for student in students
                        ])
                    messages.success(request, f"Fees assigned to {students.count()} student(s).")
                    return redirect("finance:fee_assignment")
    else:
        form = FeeAssignmentForm(user=request.user)

    central = request.user.is_superuser or getattr(request.user, "is_central_admin", False)
    assignments = FeeAssignment.objects.select_related("campus", "student", "created_by")
    if not central:
        assignments = assignments.filter(campus_id=request.user.campus_id)
    assignments = assignments[:100]
    return render(request, "finance/fee_assignment.html", {
        "form": form, "assignments": assignments,
        "is_central_admin": central,
    })
