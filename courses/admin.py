from django.contrib import admin
from .models import Course, CourseEnrollment


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "course_code", "course_title", "credit_units",
        "department", "lecturer", "semester", "is_active"
    )
    list_filter = ("department", "semester", "is_active")
    search_fields = ("course_code", "course_title", "department")


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "date_enrolled", "is_active")
    list_filter = ("course", "is_active")
    search_fields = (
        "student__registration_number",
        "course__course_code",
        "course__course_title"
    )
