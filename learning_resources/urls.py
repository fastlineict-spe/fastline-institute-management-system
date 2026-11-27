from django.urls import path
from . import views
from . import student_views

app_name = "learning_resources"

urlpatterns = [
    path("tutor/", views.tutor_materials, name="tutor_materials"),
    path("upload/<int:course_id>/", views.upload_material, name="upload_material"),
    path("course/<int:course_id>/", views.course_materials, name="course_materials"),
    path("student/", student_views.student_resources, name="student_resources"),
]
