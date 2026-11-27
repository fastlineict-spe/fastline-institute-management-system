from django.urls import path
from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.application_form, name="apply"),
    path("submitted/", views.application_submitted, name="submitted"),
    path("applications/", views.application_list, name="list"),
    path("applications/<int:pk>/", views.application_detail, name="detail"),
    path("applications/<int:pk>/approve/", views.approve_application, name="approve"),
    path("applications/<int:pk>/reject/", views.reject_application, name="reject"),
    path("applications/<int:pk>/delete/", views.delete_application, name="delete"),
    path("applications/pdf/", views.application_list_pdf, name="pdf"),
]
