from django.urls import path
from . import views
from .home import home

app_name = "dashboard"

urlpatterns = [
    path("", home, name="home"),
    path("administrator/", views.administrator_dashboard, name="administrator"),
    path("administrator/campus/<str:campus_code>/", views.administrator_dashboard, name="campus_dashboard"),
    path("lecturer/", views.lecturer_dashboard, name="lecturer"),
]
