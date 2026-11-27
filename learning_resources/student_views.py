from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from students.models import Student
from courses.models import CourseEnrollment
from .models import LearningMaterial

@login_required
def student_resources(request):
    if request.user.role != "STUDENT":
        return HttpResponseForbidden("Students only.")

    student = get_object_or_404(
        Student,
        user=request.user,
        status="ACTIVE"
    )

    materials = LearningMaterial.objects.filter(
        course__enrollments__student=student,
        course__enrollments__is_active=True,
        course__is_active=True,
        is_published=True
    ).select_related(
        "course",
        "uploaded_by"
    ).distinct().order_by("-date_uploaded")

    return render(
        request,
        "learning_resources/student_resources.html",
        {
            "student": student,
            "materials": materials,
        }
    )
