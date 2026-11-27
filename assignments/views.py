from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseForbidden
from django.utils import timezone
from courses.models import Course
from .models import Assignment, RubricCriterion


def lecturer_courses(user):
    courses = Course.objects.filter(is_active=True)

    if user.role == "ADMINISTRATOR":
        if user.is_superuser or user.is_central_admin:
            return courses
        if not user.campus_id:
            return courses.none()
        return courses.filter(campus_id=user.campus_id)

    if not user.campus_id:
        return courses.none()

    return courses.filter(
        lecturer=user,
        campus_id=user.campus_id
    )


@login_required
def lecturer_assignments(request):
    if request.user.role not in ["LECTURER", "ADMINISTRATOR"]:
        return HttpResponseForbidden("Lecturers only.")

    courses = lecturer_courses(request.user)

    assignments = Assignment.objects.filter(
        course__in=courses
    ).select_related("course", "created_by").prefetch_related(
        "submissions"
    ).order_by("-date_created")

    return render(request, "assignments/lecturer_assignments.html", {
        "assignments": assignments,
        "courses": courses,
    })


@login_required
def create_assignment(request):
    if request.user.role not in ["LECTURER", "ADMINISTRATOR"]:
        return HttpResponseForbidden("Lecturers only.")

    courses = lecturer_courses(request.user)
    error = ""

    if request.method == "POST":
        course_id = request.POST.get("course")
        course = get_object_or_404(courses, id=course_id)

        title = request.POST.get("title", "").strip()
        instructions = request.POST.get("instructions", "").strip()
        due_value = request.POST.get("due_date", "").strip()
        marks_value = request.POST.get("max_marks", "100").strip()
        attachment = request.FILES.get("attachment")
        published = request.POST.get("is_published") == "on"
        rubric_text = request.POST.get("rubric", "").strip()

        try:
            due_date = datetime.fromisoformat(due_value)
            if timezone.is_naive(due_date):
                due_date = timezone.make_aware(due_date)
            max_marks = float(marks_value)

            if not title or not instructions:
                raise ValueError("Enter the assignment title and instructions.")

            if max_marks <= 0:
                raise ValueError("Maximum marks must be greater than zero.")

            assignment = Assignment.objects.create(
                course=course,
                title=title,
                instructions=instructions,
                due_date=due_date,
                max_marks=max_marks,
                attachment=attachment,
                is_published=published,
                created_by=request.user,
            )

            for number, line in enumerate(rubric_text.splitlines(), start=1):
                if not line.strip():
                    continue

                parts = [part.strip() for part in line.split("|", 2)]

                if len(parts) < 2:
                    continue

                try:
                    criterion_marks = float(parts[1])
                except ValueError:
                    continue

                if criterion_marks > 0:
                    RubricCriterion.objects.create(
                        assignment=assignment,
                        title=parts[0],
                        maximum_marks=criterion_marks,
                        description=parts[2] if len(parts) > 2 else "",
                        order=number,
                    )

            return redirect("assignments:lecturer_assignments")

        except (ValueError, TypeError) as exc:
            error = str(exc) or "Please enter valid assignment details."

    return render(request, "assignments/create_assignment.html", {
        "courses": courses,
        "error": error,
    })


@login_required
def student_assignments(request):
    if request.user.role != "STUDENT":
        return HttpResponseForbidden("Students only.")

    from students.models import Student
    from courses.models import CourseEnrollment
    from .models import AssignmentSubmission
    from django.db.models import Prefetch

    student = get_object_or_404(
        Student, user=request.user, status="ACTIVE"
    )

    my_submissions = AssignmentSubmission.objects.filter(
        student=student
    ).prefetch_related("files")

    assignments = Assignment.objects.filter(
        course__enrollments__student=student,
        course__campus_id=student.campus_id,
        course__enrollments__is_active=True,
        course__is_active=True,
        is_published=True
    ).select_related("course").prefetch_related(
        Prefetch(
            "submissions",
            queryset=my_submissions,
            to_attr="my_submissions"
        )
    ).distinct().order_by("due_date")

    return render(request, "assignments/student_assignments.html", {
        "student": student,
        "assignments": assignments,
    })


@login_required
def assignment_detail(request, assignment_id):
    from pathlib import Path
    from students.models import Student
    from .models import AssignmentSubmission, SubmissionFile

    if request.user.role != "STUDENT":
        return HttpResponseForbidden("Students only.")

    student = get_object_or_404(
        Student, user=request.user, status="ACTIVE"
    )

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        is_published=True,
        course__enrollments__student=student,
        course__campus_id=student.campus_id,
        course__enrollments__is_active=True,
        course__is_active=True
    )

    submission = AssignmentSubmission.objects.filter(
        assignment=assignment,
        student=student
    ).prefetch_related("files").first()

    error = ""

    if request.method == "POST":
        uploaded_files = request.FILES.getlist("files")
        now = timezone.now()
        is_late = now > assignment.due_date

        if not uploaded_files:
            error = "Please select at least one coursework file."
        elif is_late and not assignment.allow_late_submissions:
            error = "The submission deadline has passed."
        else:
            allowed_extensions = {
                ".pdf", ".doc", ".docx", ".ppt", ".pptx",
                ".xls", ".xlsx", ".txt", ".jpg", ".jpeg", ".png"
            }

            for uploaded_file in uploaded_files:
                extension = Path(uploaded_file.name).suffix.lower()

                if extension not in allowed_extensions:
                    error = "Unsupported file type: " + uploaded_file.name
                    break

                if uploaded_file.size > 15 * 1024 * 1024:
                    error = "Each file must be 15 MB or smaller."
                    break

            if not error:
                if submission and submission.status in [
                    AssignmentSubmission.Status.MARKED,
                    AssignmentSubmission.Status.RETURNED
                ]:
                    error = "This coursework has already been marked. Contact your lecturer if you need to resubmit."
                else:
                    if submission:
                        for old_file in submission.files.all():
                            old_file.file.delete(save=False)
                            old_file.delete()

                        submission.submitted_at = now
                        submission.status = (
                            AssignmentSubmission.Status.LATE
                            if is_late else AssignmentSubmission.Status.SUBMITTED
                        )
                        submission.save(update_fields=["submitted_at", "status"])
                    else:
                        submission = AssignmentSubmission.objects.create(
                            assignment=assignment,
                            student=student,
                            status=(
                                AssignmentSubmission.Status.LATE
                                if is_late else AssignmentSubmission.Status.SUBMITTED
                            )
                        )

                    for uploaded_file in uploaded_files:
                        SubmissionFile.objects.create(
                            submission=submission,
                            file=uploaded_file,
                            original_name=uploaded_file.name
                        )

                    return redirect(
                        "assignments:assignment_detail",
                        assignment_id=assignment.id
                    )

    return render(request, "assignments/assignment_detail.html", {
        "student": student,
        "assignment": assignment,
        "submission": submission,
        "error": error,
        "now": timezone.now(),
    })