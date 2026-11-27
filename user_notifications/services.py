from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import User
from students.models import Student

from .models import Announcement, UserNotification


@transaction.atomic
def publish_announcement(announcement, publisher=None):
    """
    Publish an announcement to eligible users within its campus scope.
    A NULL campus means a global announcement.
    """

    announcement = Announcement.objects.select_for_update().get(
        pk=announcement.pk
    )

    if announcement.is_published:
        return 0

    if publisher is not None:
        if (
            not publisher.is_authenticated
            or not publisher.is_active
            or publisher.role != "ADMINISTRATOR"
        ):
            raise PermissionDenied

        is_central = publisher.is_superuser or publisher.is_central_admin

        if not is_central:
            if (
                publisher.campus_id is None
                or announcement.campus_id != publisher.campus_id
            ):
                raise PermissionDenied(
                    "You cannot publish announcements outside your campus."
                )

    recipients = User.objects.filter(is_active=True)

    if announcement.campus_id is not None:
        recipients = recipients.filter(
            campus_id=announcement.campus_id
        )

    students = Student.objects.filter(
        status=Student.Status.ACTIVE,
        user__isnull=False,
        user__is_active=True,
    )

    if announcement.campus_id is not None:
        students = students.filter(
            campus_id=announcement.campus_id
        )

    if announcement.audience == Announcement.Audience.ALL_USERS:
        lecturer_ids = recipients.filter(
            role="LECTURER"
        ).values_list("id", flat=True)

        admin_ids = recipients.filter(
            role="ADMINISTRATOR"
        ).values_list("id", flat=True)

        student_ids = students.values_list("user_id", flat=True)

        eligible_ids = (
            set(lecturer_ids)
            | set(admin_ids)
            | set(student_ids)
        )

    elif announcement.audience == Announcement.Audience.STUDENTS:
        eligible_ids = set(
            students.values_list("user_id", flat=True)
        )

    elif announcement.audience == Announcement.Audience.LECTURERS:
        eligible_ids = set(
            recipients.filter(
                role="LECTURER"
            ).values_list("id", flat=True)
        )

    elif announcement.audience == Announcement.Audience.SPECIFIC_STUDENTS:
        if announcement.programme:
            students = students.filter(
                programme=announcement.programme
            )

        if announcement.year_of_study:
            students = students.filter(
                year_of_study=announcement.year_of_study
            )

        if announcement.semester:
            from courses.models import Course

            enrolled_student_ids = Course.objects.filter(
                semester=announcement.semester,
                is_active=True,
                enrollments__is_active=True,
            ).values_list(
                "enrollments__student_id",
                flat=True
            )

            students = students.filter(
                id__in=enrolled_student_ids
            )

        eligible_ids = set(
            students.values_list("user_id", flat=True)
        )

    else:
        eligible_ids = set()

    if publisher is not None:
        eligible_ids.discard(publisher.id)

    notifications = [
        UserNotification(
            recipient_id=user_id,
            announcement=announcement,
            title=announcement.title,
            message=announcement.message,
        )
        for user_id in eligible_ids
    ]

    UserNotification.objects.bulk_create(notifications)

    announcement.is_published = True
    announcement.published_at = timezone.now()
    announcement.save(
        update_fields=["is_published", "published_at"]
    )

    return len(notifications)
