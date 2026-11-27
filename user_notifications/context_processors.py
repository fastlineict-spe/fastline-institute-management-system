from .models import UserNotification


def notification_context(request):
    user = request.user

    if not user.is_authenticated or not user.is_active:
        return {
            "global_notifications": [],
            "global_unread_count": 0,
        }

    eligible = user.role in ["ADMINISTRATOR", "LECTURER"]

    if user.role == "STUDENT":
        from students.models import Student

        eligible = Student.objects.filter(
            user=user,
            status=Student.Status.ACTIVE,
        ).exists()

    if not eligible:
        return {
            "global_notifications": [],
            "global_unread_count": 0,
        }

    unread = UserNotification.objects.filter(
        recipient=user,
        is_read=False,
    )

    return {
        "global_notifications": unread[:5],
        "global_unread_count": unread.count(),
    }