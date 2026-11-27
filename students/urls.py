
from django.urls import path
from . import views

app_name = "students"

urlpatterns = [
    path("register/", views.register_student, name="register"),
    path("records/", views.student_records, name="records"),
    path(
        "<int:student_id>/success/",
        views.registration_success,
        name="success",
    ),
    path(
        "<int:student_id>/download/",
        views.download_student_confirmation,
        name="download",
    ),
path("<int:student_id>/status/", views.student_status_action, name="status"),
    path("<int:student_id>/delete/", views.student_delete, name="delete"),
    path("dashboard/", views.student_dashboard, name="dashboard"),
]

