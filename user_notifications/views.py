from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db.models import Q

from accounts.models import Campus
from courses.models import Course
from students.models import Student

from .models import Announcement, UserNotification
from .services import publish_announcement


def administrator_required(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.role == "ADMINISTRATOR"
    )


def is_central_administrator(user):
    return user.is_superuser or user.is_central_admin


def announcement_queryset_for(user):
    announcements = Announcement.objects.select_related(
        "created_by", "campus"
    )

    if is_central_administrator(user):
        return announcements

    if user.campus_id is None:
        raise PermissionDenied(
            "Your administrator account has no assigned campus."
        )

    return announcements.filter(
        Q(campus_id=user.campus_id) | Q(campus__isnull=True)
    )


@login_required
def announcement_list(request):
    if not administrator_required(request.user):
        raise PermissionDenied

    announcements = announcement_queryset_for(
        request.user
    ).all()

    return render(
        request,
        "user_notifications/announcement_list.html",
        {"announcements": announcements},
    )


@login_required
def create_announcement(request):
    if not administrator_required(request.user):
        raise PermissionDenied

    central_admin = is_central_administrator(request.user)

    if not central_admin and request.user.campus_id is None:
        raise PermissionDenied(
            "Your administrator account has no assigned campus."
        )

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        message = request.POST.get("message", "").strip()
        audience = request.POST.get("audience", "")
        programme = request.POST.get("programme", "").strip()
        year = request.POST.get("year_of_study", "").strip()
        semester = request.POST.get("semester", "").strip()

        valid_audiences = [
            choice[0] for choice in Announcement.Audience.choices
        ]

        valid_semesters = [
            choice[0] for choice in Course.SemesterChoices.choices
        ]

        campus = None

        if central_admin:
            campus_id = request.POST.get("campus_id", "").strip()

            if campus_id:
                campus = Campus.objects.filter(
                    pk=campus_id,
                    is_active=True
                ).first()

                if campus is None:
                    messages.error(
                        request,
                        "Select a valid active campus."
                    )
        else:
            campus = request.user.campus

        if not title or not message:
            messages.error(
                request,
                "Enter both the announcement title and message."
            )

        elif audience not in valid_audiences:
            messages.error(
                request,
                "Select a valid announcement audience."
            )

        elif audience == Announcement.Audience.SPECIFIC_STUDENTS and (
            (year and (not year.isdigit() or int(year) < 1))
            or (semester and semester not in valid_semesters)
        ):
            messages.error(
                request,
                "Check the year and semester selections."
            )

        elif central_admin and request.POST.get("campus_id", "").strip() and campus is None:
            pass

        else:
            announcement = Announcement.objects.create(
                title=title,
                message=message,
                campus=campus,
                audience=audience,
                programme=programme,
                year_of_study=int(year) if year else None,
                semester=semester,
                created_by=request.user,
            )

            try:
                count = publish_announcement(
                    announcement,
                    publisher=request.user,
                )
            except Exception:
                announcement.delete()
                raise

            messages.success(
                request,
                f"Announcement published successfully. {count} recipients notified."
            )

            return redirect(
                "user_notifications:announcement_list"
            )

    context = {
        "audiences": Announcement.Audience.choices,
        "semesters": Course.SemesterChoices.choices,
        "is_central_admin": central_admin,
        "campuses": (
            Campus.objects.filter(is_active=True).order_by("name")
            if central_admin else []
        ),
    }

    return render(
        request,
        "user_notifications/create_announcement.html",
        context,
    )


@login_required
def student_notifications(request):
    if (
        not request.user.is_active
        or request.user.role not in [
            "STUDENT", "LECTURER", "ADMINISTRATOR"
        ]
    ):
        messages.error(
            request,
            "You are not authorised to access this page."
        )
        return redirect("accounts:login")

    if request.user.role == "STUDENT":
        student = Student.objects.filter(
            user=request.user,
            status=Student.Status.ACTIVE
        ).first()

        if not student:
            messages.error(
                request,
                "Your student account is not currently active."
            )
            return redirect("accounts:login")

    notifications = UserNotification.objects.filter(
        recipient=request.user
    ).select_related("announcement")

    unread_count = notifications.filter(is_read=False).count()

    return render(
        request,
        "user_notifications/student_notifications.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
    )


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    if (
        not request.user.is_active
        or request.user.role not in [
            "STUDENT", "LECTURER", "ADMINISTRATOR"
        ]
    ):
        messages.error(
            request,
            "You are not authorised to perform this action."
        )
        return redirect("accounts:login")

    if request.user.role == "STUDENT":
        student = Student.objects.filter(
            user=request.user,
            status=Student.Status.ACTIVE
        ).first()

        if not student:
            messages.error(
                request,
                "You are not authorised to perform this action."
            )
            return redirect("accounts:login")

    notification = get_object_or_404(
        UserNotification,
        id=notification_id,
        recipient=request.user
    )

    notification.is_read = True
    notification.save(update_fields=["is_read"])

    return redirect(
        "user_notifications:student_notifications"
    )
