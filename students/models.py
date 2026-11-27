
from django.db import models
from django.conf import settings


class Student(models.Model):

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        SUSPENDED = "SUSPENDED", "Suspended"
        DEFERRED = "DEFERRED", "Deferred"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        GRADUATED = "GRADUATED", "Graduated"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        null=True,
        blank=True
    )

    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="students",
        null=True,
        blank=True
    )

    registration_number = models.CharField(
        max_length=30,
        unique=True
    )

    date_of_birth = models.DateField(
        null=True,
        blank=True
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices
    )

    programme = models.CharField(max_length=150)
    year_of_study = models.PositiveIntegerField(default=1)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    date_registered = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.registration_number} - {self.user}"
