from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect

from students.models import Student
from accounts.models import User
from .models import Course, CourseEnrollment
from .forms import CourseForm


def is_central_admin(user):
    return user.is_superuser or user.is_central_admin


def require_course_admin(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied

    if user.role != "ADMINISTRATOR" and not user.is_superuser:
        raise PermissionDenied

    if not is_central_admin(user) and not user.campus_id:
        raise PermissionDenied


@login_required
def my_courses(request):
    if request.user.role != "STUDENT" or not request.user.is_active:
        raise PermissionDenied

    student = get_object_or_404(
        Student,
        user=request.user,
        status="ACTIVE"
    )

    try:
        selected_year = int(
            request.GET.get("year", student.year_of_study)
        )
    except (ValueError, TypeError):
        selected_year = student.year_of_study

    if selected_year not in [1, 2]:
        selected_year = student.year_of_study

    selected_semester = request.GET.get("semester", "SEMESTER 1")
    valid_semesters = ["SEMESTER 1", "SEMESTER 2", "SEMESTER 3"]

    if selected_semester not in valid_semesters:
        selected_semester = "SEMESTER 1"

    enrollments = CourseEnrollment.objects.filter(
        student=student,
        is_active=True,
        course__is_active=True,
        course__campus_id=student.campus_id,
        course__year_of_study=selected_year,
        course__semester=selected_semester
    ).select_related("course", "course__lecturer", "course__campus")

    return render(request, "courses/my_courses.html", {
        "student": student,
        "enrollments": enrollments,
        "selected_year": selected_year,
        "selected_semester": selected_semester,
        "total_courses": enrollments.count(),
    })


@login_required
def manage_course_units(request):
    require_course_admin(request.user)

    courses = Course.objects.select_related(
        "lecturer", "campus"
    )

    if not is_central_admin(request.user):
        courses = courses.filter(campus_id=request.user.campus_id)

    return render(request, "courses/admin_course_units.html", {
        "courses": courses,
        "total_courses": courses.count(),
    })


@login_required
def create_course_unit(request):
    require_course_admin(request.user)

    form = CourseForm(
        request.POST or None,
        user=request.user
    )

    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)

        if not is_central_admin(request.user):
            course.campus = request.user.campus

        if not course.campus_id:
            raise PermissionDenied

        if course.lecturer and (
            course.lecturer.campus_id != course.campus_id
        ):
            raise PermissionDenied

        course.save()
        return redirect("courses:manage_course_units")

    return render(request, "courses/course_form.html", {
        "form": form,
        "page_title": "Register Course Unit",
    })


@login_required
def edit_course_unit(request, course_id):
    require_course_admin(request.user)

    courses = Course.objects.select_related("campus", "lecturer")

    if not is_central_admin(request.user):
        courses = courses.filter(campus_id=request.user.campus_id)

    course = get_object_or_404(courses, pk=course_id)

    form = CourseForm(
        request.POST or None,
        instance=course,
        user=request.user
    )

    if request.method == "POST" and form.is_valid():
        updated_course = form.save(commit=False)

        if not is_central_admin(request.user):
            updated_course.campus = request.user.campus

        if not updated_course.campus_id:
            raise PermissionDenied

        if updated_course.lecturer and (
            updated_course.lecturer.campus_id != updated_course.campus_id
        ):
            raise PermissionDenied

        updated_course.save()
        return redirect("courses:manage_course_units")

    return render(request, "courses/course_form.html", {
        "form": form,
        "page_title": "Edit Course Unit",
    })
