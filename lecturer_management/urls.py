from django.urls import path
from . import views

app_name = "lecturers"

urlpatterns = [
    path("", views.lecturer_list, name="list"),
    path("register/", views.lecturer_create, name="create"),
    path("<int:user_id>/edit/", views.lecturer_edit, name="edit"),
    path("<int:user_id>/toggle/", views.lecturer_toggle, name="toggle"),
    path("<int:user_id>/delete/", views.lecturer_delete, name="delete"),
]
