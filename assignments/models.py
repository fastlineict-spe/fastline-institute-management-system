from django.db import models
from django.conf import settings
from django.utils import timezone


class Assignment(models.Model):
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="assignments"
    )
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    attachment = models.FileField(
        upload_to="assignment_questions/%Y/%m/",
        blank=True,
        null=True
    )
    due_date = models.DateTimeField()
    max_marks = models.DecimalField(max_digits=7, decimal_places=2, default=100)
    allow_late_submissions = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_assignments"
    )
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.title} - {self.course.course_code}"

    @property
    def is_overdue(self):
        return timezone.now() > self.due_date


class AssignmentSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        LATE = "LATE", "Late"
        MARKED = "MARKED", "Marked"
        RETURNED = "RETURNED", "Returned"

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions"
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="assignment_submissions"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SUBMITTED
    )
    marks_awarded = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True
    )
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions"
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_student_assignment_submission"
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name="files"
    )
    file = models.FileField(upload_to="coursework_submissions/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or self.file.name


class RubricCriterion(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="rubric_criteria"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    maximum_marks = models.DecimalField(max_digits=7, decimal_places=2)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.title} - {self.assignment.title}"


class SubmissionCriterionScore(models.Model):
    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name="criterion_scores"
    )
    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE,
        related_name="scores"
    )
    marks_awarded = models.DecimalField(max_digits=7, decimal_places=2)
    lecturer_comment = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "criterion"],
                name="unique_submission_rubric_criterion"
            )
        ]

    def __str__(self):
        return f"{self.criterion.title}: {self.marks_awarded}"