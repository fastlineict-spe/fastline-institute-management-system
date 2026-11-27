from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.http import Http404

from students.models import Student
from accounts.models import User, Campus
from courses.models import Course
from live_classrooms.models import LiveClassroom


@login_required
def administrator_dashboard(request, campus_code=None):
    user = request.user

    if not user.is_active or not (
        user.is_superuser or user.role == "ADMINISTRATOR"
    ):
        raise PermissionDenied

    is_central = user.is_central_admin

    if campus_code is None and is_central:
        campuses = Campus.objects.filter(is_active=True).order_by("name")
        return render(request, "dashboard/command_centre.html", {
            "campuses": campuses,
        })

    if campus_code is None:
        campus = user.campus
    else:
        campus = Campus.objects.filter(
            code__iexact=campus_code,
            is_active=True
        ).first()

    if campus is None:
        raise Http404("Campus not found.")

    if not is_central and user.campus_id != campus.id:
        raise PermissionDenied

    students = Student.objects.filter(campus=campus)
    lecturers = User.objects.filter(
        role="LECTURER", is_active=True, campus=campus
    )
    courses = Course.objects.filter(
        lecturer__campus=campus, is_active=True
    ).distinct()

    context = {
        "campus": campus,
        "is_central_admin": is_central,
        "total_students": students.count(),
        "total_lecturers": lecturers.count(),
        "total_courses": courses.count(),
        "pending_assignments": 0,
        "recent_students": students.select_related(
            "user"
        ).order_by("-date_registered")[:5],
    }

    return render(request, "dashboard/administrator.html", context)


@login_required
def lecturer_dashboard(request):
    if not request.user.is_active or request.user.role != "LECTURER":
        raise PermissionDenied

    assigned_courses = Course.objects.filter(
        lecturer=request.user,
        is_active=True
    ).order_by("year_of_study", "semester", "course_title")

    classrooms = LiveClassroom.objects.filter(
        course__lecturer=request.user,
        course__is_active=True,
        status=LiveClassroom.Status.SCHEDULED
    ).select_related(
        "course", "course__lecturer"
    ).order_by("start_time")

    context = {
        "assigned_courses": assigned_courses,
        "total_courses": assigned_courses.count(),
        "classrooms": classrooms,
    }

    return render(
        request,
        "dashboard/lecturer.html",
        context
    )