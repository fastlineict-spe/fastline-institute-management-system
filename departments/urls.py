from django.urls import path
from . import views

app_name = "departments"

urlpatterns = [
    path("", views.department_list, name="list"),
    path("create/", views.department_create, name="create"),
    path("<int:department_id>/edit/", views.department_edit, name="edit"),
    path("<int:department_id>/toggle/", views.department_toggle, name="toggle"),
    path("<int:department_id>/delete/", views.department_delete, name="delete"),
]
