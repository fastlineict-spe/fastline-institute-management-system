from django.db import models
from django.conf import settings


class CalendarEvent(models.Model):

    class EventType(models.TextChoices):
        ACADEMIC = "ACADEMIC", "Academic Event"
        ASSIGNMENT = "ASSIGNMENT", "Assignment Deadline"
        EXAMINATION = "EXAMINATION", "Examination"
        REGISTRATION = "REGISTRATION", "Registration"
        SEMESTER = "SEMESTER", "Semester Event"
        GENERAL = "GENERAL", "General Announcement"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.ACADEMIC
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    semester = models.CharField(max_length=20, blank=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return self.title
