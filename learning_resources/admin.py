from django.contrib import admin
from .models import LearningMaterial


@admin.register(LearningMaterial)
class LearningMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "material_type", "uploaded_by", "is_published", "date_uploaded")
    list_filter = ("material_type", "is_published", "course")
    search_fields = ("title", "course__course_code", "course__course_title")