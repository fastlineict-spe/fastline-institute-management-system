import secrets
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class FeeAssignment(models.Model):
    class AssignmentType(models.TextChoices):
        CLASS = "CLASS", "Class"
        INDIVIDUAL = "INDIVIDUAL", "Individual student"

    class Semester(models.TextChoices):
        ONE = "SEMESTER 1", "Semester 1"
        TWO = "SEMESTER 2", "Semester 2"
        THREE = "SEMESTER 3", "Semester 3"

    campus = models.ForeignKey("accounts.Campus", on_delete=models.PROTECT, related_name="fee_assignments")
    assignment_type = models.CharField(max_length=12, choices=AssignmentType.choices)
    programme = models.CharField(max_length=150, blank=True)
    year_of_study = models.PositiveSmallIntegerField(null=True, blank=True)
    student = models.ForeignKey("students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="individual_fee_assignments")
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, choices=Semester.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_fee_assignments")
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["campus", "academic_year", "semester"])]

    def __str__(self):
        return f"{self.get_assignment_type_display()} - {self.campus.name} - UGX {self.amount}"


class StudentFeeCharge(models.Model):
    """Immutable per-student charge snapshot used later for balances, receipts and defaulter reports."""
    assignment = models.ForeignKey(FeeAssignment, on_delete=models.PROTECT, related_name="student_charges")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="fee_charges")
    campus = models.ForeignKey("accounts.Campus", on_delete=models.PROTECT, related_name="student_fee_charges")
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, choices=FeeAssignment.Semester.choices)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["assignment", "student"], name="uniq_fee_assignment_student")
        ]

    def __str__(self):
        return f"{self.student.registration_number} - UGX {self.amount}"

class Payment(models.Model):
    """Record of money received from a student."""

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MTN_MOMO = "MTN_MOMO", "MTN Mobile Money"
        AIRTEL_MONEY = "AIRTEL_MONEY", "Airtel Money"
        BANK = "BANK", "Bank"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="finance_payments"
    )
    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="finance_payments"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    receipt_number = models.CharField(max_length=40, unique=True)
    verification_token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe, editable=False)
    transaction_reference = models.CharField(max_length=100, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    semester = models.CharField(max_length=20, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_fims_payments"
    )

    paid_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at", "-id"]
        indexes = [
            models.Index(fields=["campus", "paid_at"]),
            models.Index(fields=["student", "paid_at"]),
        ]

    def __str__(self):
        return f"{self.receipt_number} - {self.student.registration_number} - UGX {self.amount}"
