from django.db import models
from django.conf import settings


class Announcement(models.Model):

    class Audience(models.TextChoices):
        ALL_USERS = "ALL_USERS", "All eligible users"
        STUDENTS = "STUDENTS", "All active students"
        LECTURERS = "LECTURERS", "All lecturers"
        SPECIFIC_STUDENTS = "SPECIFIC_STUDENTS", "Specific student group"

    title = models.CharField(max_length=200)
    message = models.TextField()

    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="announcements",
        null=True,
        blank=True,
    )

    audience = models.CharField(
        max_length=30,
        choices=Audience.choices,
        default=Audience.ALL_USERS
    )

    programme = models.CharField(max_length=150, blank=True)
    year_of_study = models.PositiveIntegerField(null=True, blank=True)
    semester = models.CharField(max_length=30, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_announcements"
    )

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return self.title


class UserNotification(models.Model):

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True
    )

    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.title} - {self.recipient}"
