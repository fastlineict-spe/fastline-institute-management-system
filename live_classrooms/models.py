from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class LiveClassroom(models.Model):

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.PROTECT,
        related_name="live_classrooms"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    zoom_link = models.URLField(
        max_length=500,
        help_text="Paste the Zoom meeting invitation link."
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SCHEDULED
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_live_classrooms"
    )

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    def clean(self):
        super().clean()

        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValidationError({
                    "end_time": "The end time must be after the start time."
                })

        if self.course_id and not self.course.lecturer:
            raise ValidationError({
                "course": "Assign a lecturer to this course before scheduling a live classroom."
            })

    @property
    def lecturer(self):
        return self.course.lecturer

    def __str__(self):
        return f"{self.course.course_code} - {self.title}"
