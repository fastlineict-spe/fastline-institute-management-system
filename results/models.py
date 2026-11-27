from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

from courses.models import Course
from students.models import Student


class StudentResult(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted for Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Returned for Correction"
        PUBLISHED = "PUBLISHED", "Published"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="results"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="student_results"
    )
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20)

    coursework_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )
    examination_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )
    total_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=0
    )

    grade = models.CharField(max_length=5, blank=True)
    grade_point = models.DecimalField(
        max_digits=4, decimal_places=2, default=0
    )
    lecturer_comment = models.TextField(blank=True)

    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )

    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="entered_student_results"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="submitted_student_results"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="approved_student_results"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_comment = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="published_student_results"
    )

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["academic_year", "semester", "course__course_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course", "academic_year", "semester"],
                name="unique_student_course_semester_result"
            ),
            models.CheckConstraint(
                condition=Q(coursework_marks__gte=0, coursework_marks__lte=40),
                name="result_coursework_between_0_40"
            ),
            models.CheckConstraint(
                condition=Q(examination_marks__gte=0, examination_marks__lte=60),
                name="result_exam_between_0_60"
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.coursework_marks is not None:
            if not 0 <= self.coursework_marks <= 40:
                errors["coursework_marks"] = (
                    "Coursework must be between 0 and 40."
                )

        if self.examination_marks is not None:
            if not 0 <= self.examination_marks <= 60:
                errors["examination_marks"] = (
                    "Examination must be between 0 and 60."
                )

        if (
            self.student_id and self.course_id
            and self.student.campus_id and self.course.campus_id
            and self.student.campus_id != self.course.campus_id
        ):
            errors["student"] = (
                "Student and course must belong to the same campus."
            )

        if errors:
            raise ValidationError(errors)

    def calculate_total(self):
        return self.coursework_marks + self.examination_marks

    def save(self, *args, **kwargs):
        self.total_marks = self.calculate_total()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.student.registration_number} - "
            f"{self.course.course_code}"
        )


class ResultAuditLog(models.Model):

    class Action(models.TextChoices):
        CREATED = "CREATED", "Result Created"
        UPDATED = "UPDATED", "Marks Updated"
        SUBMITTED = "SUBMITTED", "Submitted for Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Returned for Correction"
        PUBLISHED = "PUBLISHED", "Published"
        UNPUBLISHED = "UNPUBLISHED", "Publication Reversed"
        IMPORTED = "IMPORTED", "Imported"

    result = models.ForeignKey(
        StudentResult, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="result_audit_actions"
    )
    campus = models.ForeignKey(
        "accounts.Campus", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="result_audit_logs"
    )

    action = models.CharField(max_length=15, choices=Action.choices)
    student_registration_number = models.CharField(max_length=30, blank=True)
    course_code = models.CharField(max_length=20, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    semester = models.CharField(max_length=20, blank=True)

    details = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.action} - {self.student_registration_number} "
            f"- {self.created_at}"
        )
