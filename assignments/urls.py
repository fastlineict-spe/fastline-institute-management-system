from django.urls import path
from . import views

app_name = "assignments"

urlpatterns = [
    path("student/", views.student_assignments, name="student_assignments"),
    path("student/<int:assignment_id>/", views.assignment_detail, name="assignment_detail"),
    path("lecturer/", views.lecturer_assignments, name="lecturer_assignments"),
    path("lecturer/create/", views.create_assignment, name="create_assignment"),
]