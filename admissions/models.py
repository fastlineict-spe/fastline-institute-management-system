from uuid import uuid4
from django.conf import settings
from django.db import models


class Application(models.Model):
    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    reference_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="admission_applications"
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    programme = models.CharField(max_length=150)
    year_of_study = models.PositiveIntegerField(default=1)
    address = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_admission_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    student = models.OneToOneField(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admission_application"
    )

    date_submitted = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference_number:
            year = self.date_submitted.year if self.date_submitted else __import__("datetime").date.today().year
            self.reference_number = f"FHI-APP-{year}-{uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-date_submitted"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.campus} ({self.status})"
