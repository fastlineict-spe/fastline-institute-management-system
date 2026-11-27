from django.db import models
from django.conf import settings


class Course(models.Model):

    class SemesterChoices(models.TextChoices):
        SEMESTER_1 = "SEMESTER 1", "Semester 1"
        SEMESTER_2 = "SEMESTER 2", "Semester 2"
        SEMESTER_3 = "SEMESTER 3", "Semester 3"

    course_code = models.CharField(max_length=20, unique=True)
    course_title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    campus = models.ForeignKey(
        "accounts.Campus",
        on_delete=models.PROTECT,
        related_name="courses",
        null=True,
        blank=True
    )

    programme = models.CharField(max_length=150, default="General")
    year_of_study = models.PositiveSmallIntegerField(default=1)

    semester = models.CharField(
        max_length=20,
        choices=SemesterChoices.choices,
        default=SemesterChoices.SEMESTER_1
    )

    credit_units = models.PositiveIntegerField(default=3)
    department = models.CharField(max_length=150, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)

    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lectured_courses"
    )

    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["year_of_study", "semester", "course_code"]
        verbose_name = "Course Unit"
        verbose_name_plural = "Course Units"

    def __str__(self):
        return f"{self.course_code} - {self.course_title}"


class CourseEnrollment(models.Model):

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="course_enrollments"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments"
    )

    date_enrolled = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course_enrollment"
            )
        ]
        ordering = ["course__course_code"]

    def __str__(self):
        return f"{self.student} - {self.course}"
