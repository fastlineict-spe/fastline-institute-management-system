from django.contrib import admin
from .models import Announcement, UserNotification


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "audience",
        "programme",
        "year_of_study",
        "semester",
        "is_published",
        "published_at",
    )

    list_filter = (
        "audience",
        "is_published",
        "year_of_study",
        "semester",
    )

    search_fields = ("title", "message", "programme")
    readonly_fields = ("date_created",)


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recipient",
        "is_read",
        "date_created",
    )

    list_filter = ("is_read", "date_created")
    search_fields = ("title", "message", "recipient__username")
    readonly_fields = ("date_created",)