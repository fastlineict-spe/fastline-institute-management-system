from django.db import models
from django.conf import settings
from courses.models import Course


class LearningMaterial(models.Model):

    class MaterialType(models.TextChoices):
        NOTES = "NOTES", "Lecture Notes"
        PRESENTATION = "PRESENTATION", "Presentation"
        READING = "READING", "Recommended Reading"
        OTHER = "OTHER", "Other Learning Material"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="learning_materials"
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    material_type = models.CharField(
        max_length=20,
        choices=MaterialType.choices,
        default=MaterialType.NOTES
    )

    file = models.FileField(upload_to="course_materials/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_learning_materials"
    )

    is_published = models.BooleanField(default=True)
    date_uploaded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_uploaded"]
        verbose_name = "Learning Material"
        verbose_name_plural = "Learning Materials"

    def __str__(self):
        return f"{self.title} - {self.course.course_code}"