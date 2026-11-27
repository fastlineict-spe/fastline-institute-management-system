from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from students.models import Student
from courses.models import Course, CourseEnrollment
from .models import LearningMaterial


@login_required
def tutor_materials(request):
    if request.user.role not in ["LECTURER", "ADMINISTRATOR"]:
        return HttpResponseForbidden("You are not authorised to access this page.")

    if request.user.role == "ADMINISTRATOR":
        courses = Course.objects.filter(is_active=True)
    else:
        courses = Course.objects.filter(lecturer=request.user, is_active=True)

    return render(request, "learning_resources/tutor_materials.html", {
        "courses": courses
    })


@login_required
def upload_material(request, course_id):
    if request.user.role not in ["LECTURER", "ADMINISTRATOR"]:
        return HttpResponseForbidden("You are not authorised to upload materials.")

    course = get_object_or_404(Course, id=course_id, is_active=True)

    if request.user.role == "LECTURER" and course.lecturer_id != request.user.id:
        return HttpResponseForbidden("This course unit is not assigned to you.")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        material_type = request.POST.get("material_type", "NOTES")
        uploaded_file = request.FILES.get("file")

        valid_types = [choice[0] for choice in LearningMaterial.MaterialType.choices]

        if title and uploaded_file and material_type in valid_types:
            LearningMaterial.objects.create(
                course=course,
                title=title,
                description=description,
                material_type=material_type,
                file=uploaded_file,
                uploaded_by=request.user
            )
            return redirect("learning_resources:tutor_materials")

        return render(request, "learning_resources/upload_material.html", {
            "course": course,
            "error": "Enter a title, select a material type and choose a file."
        })

    return render(request, "learning_resources/upload_material.html", {
        "course": course
    })


@login_required
def course_materials(request, course_id):
    if request.user.role != "STUDENT":
        return HttpResponseForbidden("This page is for students.")

    student = get_object_or_404(Student, user=request.user, status="ACTIVE")

    enrollment = get_object_or_404(
        CourseEnrollment,
        student=student,
        course_id=course_id,
        is_active=True,
        course__is_active=True
    )

    materials = LearningMaterial.objects.filter(
        course=enrollment.course,
        is_published=True
    ).select_related("uploaded_by")

    return render(request, "learning_resources/course_materials.html", {
        "course": enrollment.course,
        "materials": materials
    })