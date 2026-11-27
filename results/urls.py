from django.urls import path
from . import views

app_name = "results"

urlpatterns = [
    path("", views.results_dashboard, name="dashboard"),
    path("student/", views.student_results, name="student_results"),
    path("course/<int:course_id>/", views.course_marks, name="course_marks"),
    path(
        "course/<int:course_id>/submit/",
        views.submit_course_results,
        name="submit_course_results",
    ),
    path("review/", views.review_results, name="review_results"),
    path(
        "review/<int:result_id>/approve/",
        views.approve_result,
        name="approve_result",
    ),
    path(
        "review/<int:result_id>/reject/",
        views.reject_result,
        name="reject_result",
    ),
    path(
        "review/<int:result_id>/publish/",
        views.publish_result,
        name="publish_result",
    ),
]
