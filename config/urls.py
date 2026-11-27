from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admissions/", include("admissions.urls")),
    path("finance/", include("finance.urls")),
    path("administrator/departments/", include("departments.urls")), 
    path("administrator/lecturers/", include("lecturer_management.urls")),
    path('messages/', include('messaging.urls')), 
    path("admin/", admin.site.urls),
    path("administrator/live-classrooms/", include("live_classrooms.urls")),
    path("", include("dashboard.urls")),
    path("students/", include("students.urls")),
    path("accounts/", include("accounts.urls")),
    path("courses/", include("courses.urls")),
    path("resources/", include("learning_resources.urls")),
    path("assignments/", include("assignments.urls")),
    path("results/", include("results.urls")),
    path("calendar/", include("study_calendar.urls")),
path("notifications/", include("user_notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


