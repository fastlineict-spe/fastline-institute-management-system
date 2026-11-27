from datetime import date

import logging
from email.mime.image import MIMEImage
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse

from accounts.models import Campus
from students.models import Student
from students.utils import generate_admission_number
from .models import Application

User = get_user_model()

logger = logging.getLogger(__name__)


def send_application_notification(application, event, admission_number=None):
    subjects = {
        "submitted": "Application Received - Fastline Institute",
        "approved": "Application Approved - Fastline Institute",
        "rejected": "Application Update - Fastline Institute",
    }

    if event not in subjects:
        return False

    context = {
        "application": application,
        "admission_number": admission_number,
    }

    try:
        text_body = render_to_string(
            f"admissions/emails/application_{event}.txt", context
        )
        html_body = render_to_string(
            f"admissions/emails/application_{event}.html", context
        )

        email = EmailMultiAlternatives(
            subject=subjects[event],
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[application.email],
        )
        email.attach_alternative(html_body, "text/html")

        logo_path = settings.BASE_DIR / "static" / "images" / "fastline-logo.jpg"
        if logo_path.is_file():
            with logo_path.open("rb") as logo_file:
                logo = MIMEImage(logo_file.read(), _subtype="jpeg")
            logo.add_header("Content-ID", "<fastline_logo>")
            logo.add_header(
                "Content-Disposition", "inline", filename="fastline-logo.jpg"
            )
            email.attach(logo)

        email.send(fail_silently=False)
        return True

    except Exception:
        logger.exception(
            "Fastline application email failed for reference %s (%s)",
            application.reference_number,
            event,
        )
        return False



def administrator_required(request):
    return (
        request.user.is_authenticated
        and (
            request.user.is_superuser
            or getattr(request.user, "role", "") == "ADMINISTRATOR"
        )
    )


def application_form(request):
    campuses = Campus.objects.filter(is_active=True)

    if request.method == "POST":
        campus = campuses.filter(
            pk=request.POST.get("campus_id")
        ).first()

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone_number", "").strip()
        gender = request.POST.get("gender", "")
        programme = request.POST.get("programme", "").strip()
        address = request.POST.get("address", "").strip()
        dob = request.POST.get("date_of_birth") or None

        try:
            year = int(request.POST.get("year_of_study", "1"))
            if year < 1:
                raise ValueError
        except ValueError:
            messages.error(request, "Enter a valid year of study.")
            return redirect("admissions:apply")

        if not campus:
            messages.error(request, "Please select a valid campus.")
        elif not all([first_name, last_name, email, phone, gender, programme]):
            messages.error(request, "Please complete all required fields.")
        elif gender not in Student.Gender.values:
            messages.error(request, "Please select a valid gender.")
        else:
            try:
                validate_email(email)

                if dob:
                    dob = date.fromisoformat(dob)
                    if dob > date.today():
                        raise ValueError

                application = Application.objects.create(
                    campus=campus,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone_number=phone,
                    gender=gender,
                    programme=programme,
                    year_of_study=year,
                    date_of_birth=dob,
                    address=address,
                )

                transaction.on_commit(
                    lambda app=application: send_application_notification(app, 'submitted')
                )

                request.session["admissions_last_reference"] = application.reference_number
                return redirect("admissions:submitted")

            except ValidationError:
                messages.error(request, "Enter a valid email address.")
            except ValueError:
                messages.error(request, "Enter a valid date of birth.")

        return redirect("admissions:apply")

    return render(request, "admissions/apply.html", {
        "campuses": campuses,
    })


def application_submitted(request):
    reference_number = request.session.get("admissions_last_reference")
    application = Application.objects.filter(
        reference_number=reference_number
    ).first() if reference_number else None

    return render(request, "admissions/submitted.html", {
        "application": application,
        "reference_number": reference_number,
    })


def accessible_applications(request):
    applications = Application.objects.select_related(
        "campus", "reviewed_by", "student"
    )

    if not request.user.is_central_admin:
        if not request.user.campus_id:
            return None
        applications = applications.filter(
            campus_id=request.user.campus_id
        )

    return applications


@login_required
def application_list(request):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to access Admissions.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    campus_code = request.GET.get("campus", "").strip()

    if search:
        applications = applications.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(programme__icontains=search)
            | Q(reference_number__icontains=search)
        )

    if status in Application.Status.values:
        applications = applications.filter(status=status)

    if request.user.is_central_admin and campus_code:
        applications = applications.filter(
            campus__code__iexact=campus_code
        )

    if request.user.campus_id:
        dashboard_campus_code = request.user.campus.code
    else:
        selected_dashboard_campus = Campus.objects.filter(
            code__iexact=campus_code,
            is_active=True,
        ).first() if request.user.is_central_admin and campus_code else None

        command_centre = Campus.objects.filter(
            is_active=True,
            is_command_centre=True,
        ).first()

        dashboard_campus_code = (
            selected_dashboard_campus.code
            if selected_dashboard_campus
            else command_centre.code if command_centre else None
        )

    return render(request, "admissions/application_list.html", {
        "applications": applications,
        "search": search,
        "selected_status": status,
        "selected_campus": campus_code,
        "campuses": Campus.objects.filter(is_active=True),
        "is_central_admin": request.user.is_central_admin,
        "dashboard_campus_code": dashboard_campus_code,
        "pending_count": applications.filter(
            status=Application.Status.PENDING
        ).count(),
    })




@login_required
def application_list_pdf(request):
    if not administrator_required(request):
        messages.error(request, "You are not authorised to download Admissions.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    campus_code = request.GET.get("campus", "").strip()

    if search:
        applications = applications.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
            | Q(programme__icontains=search)
            | Q(reference_number__icontains=search)
        )

    if status in Application.Status.values:
        applications = applications.filter(status=status)

    if request.user.is_central_admin and campus_code:
        applications = applications.filter(campus__code__iexact=campus_code)

    applications = applications.order_by("-date_submitted")

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title="Fastline Admissions Register",
        author="Fastline Institute of Higher Education",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FastlineTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#102b59"),
        alignment=TA_CENTER,
        fontSize=17,
        spaceAfter=5,
    )
    subtitle_style = ParagraphStyle(
        "FastlineSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=12,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=cell_style,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    story = [
        Paragraph("FASTLINE INSTITUTE OF HIGHER EDUCATION", title_style),
        Paragraph("I SHALL RISE &amp; SHINE", subtitle_style),
        Paragraph("ADMISSIONS REGISTER", styles["Heading2"]),
        Paragraph(
            "Generated: " + timezone.localtime().strftime("%d %b %Y, %H:%M")
            + " | Total applications: " + str(applications.count()),
            styles["Normal"],
        ),
        Spacer(1, 10),
    ]

    headers = [
        "Reference", "Applicant", "Email", "Phone",
        "Campus", "Programme", "Year", "Date Applied", "Status"
    ]

    data = [[Paragraph(escape(h), header_style) for h in headers]]

    for app in applications:
        submitted = (
            timezone.localtime(app.date_submitted).strftime("%d %b %Y")
            if app.date_submitted else ""
        )
        values = [
            app.reference_number or "",
            app.first_name + " " + app.last_name,
            app.email or "",
            app.phone_number or "",
            app.campus.name if app.campus else "",
            app.programme or "",
            str(app.year_of_study or ""),
            submitted,
            app.get_status_display(),
        ]
        data.append([
            Paragraph(escape(str(value)), cell_style)
            for value in values
        ])

    if len(data) == 1:
        data.append([
            Paragraph("No applications found.", cell_style)
        ] + [""] * 8)

    table = Table(
        data,
        repeatRows=1,
        colWidths=[83, 100, 125, 75, 75, 105, 35, 65, 65],
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102b59")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d5dce5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, colors.HexColor("#f2f5f9")
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    document.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="fastline_admissions_register.pdf"'
    return response


@login_required
def application_detail(request, pk):
    if not administrator_required(request):
        messages.error(request, "You are not authorised.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    application = get_object_or_404(applications, pk=pk)

    return render(request, "admissions/application_detail.html", {
        "application": application,
    })


@login_required
def approve_application(request, pk):
    if request.method != "POST":
        return redirect("admissions:list")

    if not administrator_required(request):
        messages.error(request, "You are not authorised.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    try:
        with transaction.atomic():
            application = get_object_or_404(
                applications.select_for_update(), pk=pk
            )

            if application.status != Application.Status.PENDING:
                messages.warning(request, "This application has already been processed.")
                return redirect("admissions:detail", pk=pk)

            admission_number = generate_admission_number()

            user = User.objects.create_user(
                username=admission_number,
                first_name=application.first_name,
                last_name=application.last_name,
                email=application.email,
                password=None,
                role="STUDENT",
                campus=application.campus,
                phone_number=application.phone_number,
            )

            student = Student.objects.create(
                user=user,
                campus=application.campus,
                registration_number=admission_number,
                date_of_birth=application.date_of_birth,
                gender=application.gender,
                programme=application.programme,
                year_of_study=application.year_of_study,
                phone_number=application.phone_number,
                address=application.address,
            )

            application.student = student
            application.status = Application.Status.APPROVED
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.rejection_reason = ""
            application.save()
            transaction.on_commit(
                lambda app=application, number=admission_number: send_application_notification(
                    app, 'approved', number
                )
            )

        messages.success(
            request,
            f"Application approved. Admission number: {admission_number}"
        )

    except IntegrityError:
        messages.error(
            request,
            "Approval could not be completed because of a duplicate account or admission number."
        )

    return redirect("admissions:detail", pk=pk)


@login_required
def reject_application(request, pk):
    if request.method != "POST":
        return redirect("admissions:list")

    if not administrator_required(request):
        messages.error(request, "You are not authorised.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    reason = request.POST.get("rejection_reason", "").strip()

    if not reason:
        messages.error(request, "Please provide a rejection reason.")
        return redirect("admissions:detail", pk=pk)

    with transaction.atomic():
        application = get_object_or_404(
            applications.select_for_update(), pk=pk
        )

        if application.status != Application.Status.PENDING:
            messages.warning(request, "This application has already been processed.")
        else:
            application.status = Application.Status.REJECTED
            application.rejection_reason = reason
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            transaction.on_commit(
                lambda app=application: send_application_notification(app, "rejected")
            )

            messages.success(request, "Application rejected.")

    return redirect("admissions:detail", pk=pk)


@login_required
def delete_application(request, pk):
    if request.method != "POST":
        return redirect("admissions:detail", pk=pk)

    if not administrator_required(request):
        messages.error(request, "You are not authorised.")
        return redirect("dashboard:administrator")

    applications = accessible_applications(request)

    if applications is None:
        messages.error(request, "Your account has no assigned campus.")
        return redirect("dashboard:administrator")

    application = get_object_or_404(applications, pk=pk)
    reference = application.reference_number

    application.delete()

    messages.success(
        request,
        f"Application {reference} has been permanently deleted. "
        "Any existing student record and account have been retained."
    )
    return redirect("admissions:list")
