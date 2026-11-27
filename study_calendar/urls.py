from django.urls import path
from . import views

app_name = "study_calendar"

urlpatterns = [
    path("student/", views.student_calendar, name="student_calendar"),
]