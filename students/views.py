
from datetime import date
from io import BytesIO
from html import escape

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from accounts.models import Campus
from .models import Student
from live_classrooms.models import LiveClassroom
from .utils import generate_admission_number

User = get_user_model()


def administrator_required(request):
    return (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or getattr(request.user, "role", "") == "ADMINISTRATOR"
        )
    )


@login_required
def student_records(request):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to view student records.")
        return redirect("dashboard:administrator")

    search_query = request.GET.get("q", "").strip()
    selected_status = request.GET.get("status", "").strip()
    is_central = request.user.is_central_admin

    students = Student.objects.select_related("user", "campus")

    if not is_central:
        if not request.user.campus_id:
            messages.error(request, "Your account has no assigned campus.")
            return redirect("dashboard:administrator")
        students = students.filter(campus_id=request.user.campus_id)
    else:
        campus_code = request.GET.get("campus", "").strip()
        if campus_code:
            students = students.filter(campus__code__iexact=campus_code)

    if search_query:
        students = students.filter(
            Q(registration_number__icontains=search_query)
            | Q(programme__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    if selected_status in Student.Status.values:
        students = students.filter(status=selected_status)

    context = {
        "students": students.order_by("registration_number"),
        "search_query": search_query,
        "selected_status": selected_status,
        "total_students": students.count(),
        "status_choices": Student.Status.choices,
        "campuses": Campus.objects.filter(is_active=True).order_by("name") if is_central else [],
        "is_central_admin": is_central,
    }

    return render(request, "students/records.html", context)


@login_required
def register_student(request):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to register students.")
        return redirect("dashboard:administrator")

    is_central = request.user.is_central_admin

    if request.method == "POST":
        if is_central:
            campus = Campus.objects.filter(
                pk=request.POST.get("campus_id"),
                is_active=True
            ).first()
        else:
            campus = request.user.campus

        if campus is None:
            messages.error(request, "Please select a valid campus.")
            return redirect("students:register")
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        gender = request.POST.get("gender", "")
        date_of_birth = request.POST.get("date_of_birth") or None
        programme = request.POST.get("programme", "").strip()
        phone_number = request.POST.get("phone_number", "").strip()
        address = request.POST.get("address", "").strip()

        try:
            year_of_study = int(request.POST.get("year_of_study", "1"))
            if year_of_study < 1:
                raise ValueError
        except ValueError:
            messages.error(request, "Enter a valid year of study.")
            return redirect("students:register")

        if not all([first_name, last_name, email, gender, programme]):
            messages.error(request, "Please complete all required fields.")
            return redirect("students:register")

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Enter a valid active email address.")
            return redirect("students:register")

        if gender not in Student.Gender.values:
            messages.error(request, "Please select a valid gender.")
            return redirect("students:register")

        if date_of_birth:
            try:
                date_of_birth = date.fromisoformat(date_of_birth)
                if date_of_birth > date.today():
                    raise ValueError
            except ValueError:
                messages.error(request, "Enter a valid date of birth.")
                return redirect("students:register")

        try:
            with transaction.atomic():
                admission_number = generate_admission_number()

                user = User.objects.create_user(
                    username=admission_number,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=None,
                    role="STUDENT",
                    campus=campus,
                )

                student = Student.objects.create(
                    user=user,
                    campus=campus,
                    registration_number=admission_number,
                    date_of_birth=date_of_birth,
                    gender=gender,
                    programme=programme,
                    year_of_study=year_of_study,
                    phone_number=phone_number,
                    address=address,
                )

            return redirect(
                "students:success",
                student_id=student.pk
            )

        except IntegrityError:
            messages.error(
                request,
                "The admission number or student account already exists. Please try again."
            )
            return redirect("students:register")

    return render(request, "students/register.html", {
        "campuses": Campus.objects.filter(is_active=True).order_by("name") if is_central else [],
        "is_central_admin": is_central,
    })


@login_required
def registration_success(request, student_id):
    if not administrator_required(request):
        return redirect("dashboard:administrator")

    student_queryset = Student.objects.all()
    if not request.user.is_central_admin:
        student_queryset = student_queryset.filter(
            campus_id=request.user.campus_id
        )
    student = get_object_or_404(student_queryset, pk=student_id)

    return render(
        request,
        "students/success.html",
        {"student": student}
    )


@login_required
def download_student_confirmation(request, student_id):
    if not administrator_required(request):
        return redirect("dashboard:administrator")

    student_queryset = Student.objects.all()
    if not request.user.is_central_admin:
        student_queryset = student_queryset.filter(
            campus_id=request.user.campus_id
        )
    student = get_object_or_404(student_queryset, pk=student_id)
    full_name = (
        student.user.get_full_name()
        if student.user
        else "Student"
    )
    email = student.user.email if student.user else ""

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Institution",
        parent=styles["Title"],
        textColor=colors.HexColor("#142747"),
        fontSize=18,
        leading=23,
        alignment=1,
    ))
    styles.add(ParagraphStyle(
        name="AdmissionNumber",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#B58A35"),
        fontSize=22,
        alignment=1,
        spaceBefore=10,
        spaceAfter=18,
    ))

    story = [
        Paragraph("FASTLINE INSTITUTE OF HIGHER EDUCATION", styles["Institution"]),
        Paragraph("LEARNING WITHOUT BOUNDARIES", styles["Normal"]),
        Spacer(1, 20),
        Paragraph("STUDENT REGISTRATION CONFIRMATION", styles["Heading2"]),
        Paragraph(escape(student.registration_number), styles["AdmissionNumber"]),
        Spacer(1, 10),
    ]

    details = [
        ["Student Name", full_name],
        ["Admission Number", student.registration_number],
        ["Email Address", email],
        ["Programme", student.programme],
        ["Year of Study", str(student.year_of_study)],
        ["Gender", student.get_gender_display()],
        ["Phone Number", student.phone_number or "Not provided"],
        ["Date of Birth", str(student.date_of_birth or "Not provided")],
        ["Registration Date", timezone.localtime(student.date_registered).strftime("%d %B %Y")],
        ["Status", student.get_status_display()],
    ]

    table = Table(
        [[Paragraph(escape(str(a)), styles["Normal"]),
          Paragraph(escape(str(b)), styles["Normal"])] for a, b in details],
        colWidths=[48 * mm, 105 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#24344D")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9E0EA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))

    story.extend([
        table,
        Spacer(1, 25),
        Paragraph(
            "This document confirms that the student has been registered "
            "in the Fastline Institute of Higher Education system.",
            styles["BodyText"],
        ),
        Spacer(1, 15),
        Paragraph("Administration Office", styles["Normal"]),
    ])

    document.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="Fastline-{student.registration_number}.pdf"'
    )
    return response

@login_required
def student_dashboard(request):
    if request.user.role != "STUDENT":
        return redirect("accounts:login")

    student = get_object_or_404(
        Student,
        user=request.user
    )

    if student.status != Student.Status.ACTIVE:
        return redirect("accounts:login")

    classrooms = LiveClassroom.objects.filter(
        course__enrollments__student=student,
        course__enrollments__is_active=True,
        course__is_active=True,
        status=LiveClassroom.Status.SCHEDULED
    ).select_related(
        "course", "course__lecturer"
    ).distinct().order_by("start_time")

    return render(
        request,
        "students/dashboard.html",
        {
            "student": student,
            "classrooms": classrooms,
        }
    )

# ============================================================
# STUDENT DEACTIVATION, REACTIVATION AND SAFE PERMANENT DELETION
# ============================================================

def _student_admin_queryset(request):
    queryset = Student.objects.select_related("user", "campus")

    if request.user.is_superuser or getattr(request.user, "is_central_admin", False):
        return queryset

    if not request.user.campus_id:
        return queryset.none()

    return queryset.filter(campus_id=request.user.campus_id)


def _student_deletion_blockers(student):
    blockers = []

    for relation in Student._meta.related_objects:
        related_model = relation.related_model
        field_name = relation.field.name

        count = related_model._base_manager.filter(
            **{field_name: student}
        ).count()

        if count:
            label = related_model._meta.verbose_name_plural
            blockers.append(f"{count} linked {label}")

    return blockers


@login_required
def student_status_action(request, student_id):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to manage student records.")
        return redirect("dashboard:administrator")

    if request.method != "POST":
        return HttpResponse("POST request required.", status=405)

    new_status = request.POST.get("status", "").strip()

    if new_status not in (Student.Status.ACTIVE, Student.Status.INACTIVE):
        messages.error(request, "Invalid student status action.")
        return redirect("students:records")

    student = get_object_or_404(
        _student_admin_queryset(request),
        pk=student_id
    )

    if student.status not in (Student.Status.ACTIVE, Student.Status.INACTIVE):
        messages.error(
            request,
            "Only active or inactive students can use this status action."
        )
        return redirect("students:records")

    student.status = new_status
    student.save(update_fields=["status"])

    if new_status == Student.Status.INACTIVE:
        messages.success(
            request,
            f"{student.registration_number} has been deactivated."
        )
    else:
        messages.success(
            request,
            f"{student.registration_number} has been reactivated."
        )

    return redirect("students:records")


@login_required
def student_delete(request, student_id):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to delete student records.")
        return redirect("dashboard:administrator")

    student = get_object_or_404(
        _student_admin_queryset(request),
        pk=student_id
    )

    blockers = _student_deletion_blockers(student)

    if request.method == "POST":
        if blockers:
            messages.error(
                request,
                "Permanent deletion blocked. This student has linked records: "
                + ", ".join(blockers)
                + ". Deactivate the student instead to preserve their history."
            )
            return redirect("students:records")

        with transaction.atomic():
            student = get_object_or_404(
                _student_admin_queryset(request).select_for_update(),
                pk=student_id
            )

            blockers = _student_deletion_blockers(student)

            if blockers:
                messages.error(
                    request,
                    "Deletion blocked because linked records now exist: "
                    + ", ".join(blockers)
                )
                return redirect("students:records")

            registration_number = student.registration_number
            student.delete()

        messages.success(
            request,
            f"Student {registration_number} was permanently deleted."
        )
        return redirect("students:records")

    return render(
        request,
        "students/delete_confirm.html",
        {
            "student": student,
            "blockers": blockers,
            "can_delete": not blockers,
        }
    )

