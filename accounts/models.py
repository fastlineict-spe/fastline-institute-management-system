from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Roles(models.TextChoices):
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
        LECTURER = "LECTURER", "Lecturer"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.STUDENT
    )

    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True
    )

    is_central_admin = models.BooleanField(default=False)

    phone_number = models.CharField(
        max_length=20,
        blank=True
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

class Campus(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    phone_primary = models.CharField(max_length=20)
    phone_secondary = models.CharField(max_length=20)
    is_command_centre = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
