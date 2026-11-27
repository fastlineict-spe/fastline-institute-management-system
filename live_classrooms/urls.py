from django.urls import path
from . import views

app_name = "live_classrooms"

urlpatterns = [
    path("", views.classroom_list, name="admin_list"),
    path("schedule/", views.classroom_create, name="create"),
    path("<int:classroom_id>/edit/", views.classroom_edit, name="edit"),
    path("<int:classroom_id>/cancel/", views.classroom_cancel, name="cancel"),
    path("<int:classroom_id>/delete/", views.classroom_delete, name="delete"),
]
