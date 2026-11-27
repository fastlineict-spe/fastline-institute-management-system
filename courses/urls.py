from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    path("my-courses/", views.my_courses, name="my_courses"),
    path("manage/", views.manage_course_units, name="manage_course_units"),
    path("manage/create/", views.create_course_unit, name="create_course_unit"),
    path("manage/<int:course_id>/edit/", views.edit_course_unit, name="edit_course_unit"),
]