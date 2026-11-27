
from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "user",
        "programme",
        "year_of_study",
        "gender",
        "status",
        "date_registered",
    )

    list_filter = ("programme", "year_of_study", "gender", "status")
    search_fields = (
        "registration_number",
        "user__first_name",
        "user__last_name",
        "user__username",
    )
    ordering = ("registration_number",)
