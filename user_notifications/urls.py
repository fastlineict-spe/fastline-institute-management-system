from django.urls import path
from . import views

app_name = "user_notifications"

urlpatterns = [
    # Administrator announcement management
    path("announcements/", views.announcement_list, name="announcement_list"),
    path("announcements/create/", views.create_announcement, name="create_announcement"),

    # Student notifications
    path("student/", views.student_notifications, name="student_notifications"),
    path(
        "student/read/<int:notification_id>/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
]