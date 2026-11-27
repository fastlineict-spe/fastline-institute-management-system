from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from courses.models import Course, CourseEnrollment
from students.models import Student
from .models import StudentResult, ResultAuditLog


def is_central_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_central_admin
    )


def require_admin(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied

    if user.role != User.Roles.ADMINISTRATOR and not user.is_superuser:
        raise PermissionDenied

    if not is_central_admin(user) and not user.campus_id:
        raise PermissionDenied


def accessible_courses(user):
    if user.role == User.Roles.LECTURER:
        if not user.campus_id:
            return Course.objects.none()

        return Course.objects.filter(
            lecturer=user,
            campus_id=user.campus_id,
            is_active=True,
        )

    require_admin(user)

    courses = Course.objects.filter(is_active=True)

    if not is_central_admin(user):
        courses = courses.filter(campus_id=user.campus_id)

    return courses


def get_accessible_course(user, course_id):
    course = get_object_or_404(
        accessible_courses(user).select_related("campus", "lecturer"),
        pk=course_id,
    )

    if (
        user.role == User.Roles.LECTURER
        and course.lecturer_id != user.id
    ):
        raise PermissionDenied

    return course


def write_audit(result, actor, action, details=None, reason=""):
    ResultAuditLog.objects.create(
        result=result,
        actor=actor,
        campus_id=result.course.campus_id,
        action=action,
        student_registration_number=result.student.registration_number,
        course_code=result.course.course_code,
        academic_year=result.academic_year,
        semester=result.semester,
        details=details or {},
        reason=reason,
    )


@login_required
def results_dashboard(request):
    if request.user.role == User.Roles.STUDENT:
        return redirect("results:student_results")

    if request.user.role not in (
        User.Roles.ADMINISTRATOR,
        User.Roles.LECTURER,
    ) and not request.user.is_superuser:
        raise PermissionDenied

    courses = accessible_courses(request.user).select_related(
        "campus", "lecturer"
    )

    if request.user.role == User.Roles.LECTURER:
        page_title = "My Assigned Course Units"
    else:
        page_title = "Results Management"

    return render(request, "results/dashboard.html", {
        "courses": courses,
        "page_title": page_title,
        "is_central_admin": is_central_admin(request.user),
    })


@login_required
def course_marks(request, course_id):
    if request.user.role not in (
        User.Roles.ADMINISTRATOR,
        User.Roles.LECTURER,
    ) and not request.user.is_superuser:
        raise PermissionDenied

    course = get_accessible_course(request.user, course_id)

    enrollments = CourseEnrollment.objects.filter(
        course=course,
        is_active=True,
        student__status=Student.Status.ACTIVE,
    ).select_related("student", "student__user").order_by(
        "student__registration_number"
    )

    academic_year = (
        request.POST.get("academic_year", "").strip()
        if request.method == "POST"
        else request.GET.get("academic_year", "").strip()
    )

    existing_results = {}

    if academic_year:
        existing_results = {
            result.student_id: result
            for result in StudentResult.objects.filter(
                course=course,
                academic_year=academic_year,
                semester=course.semester,
                student__in=[enrollment.student_id for enrollment in enrollments],
            )
        }

    if request.method == "POST":
        if not academic_year:
            messages.error(request, "Enter the academic year.")
            return redirect("results:course_marks", course_id=course.id)

        entries = []
        errors = []

        for enrollment in enrollments:
            student = enrollment.student
            cw_raw = request.POST.get(
                f"coursework_{student.id}", ""
            ).strip()
            exam_raw = request.POST.get(
                f"examination_{student.id}", ""
            ).strip()

            if not cw_raw and not exam_raw:
                continue

            if not cw_raw or not exam_raw:
                errors.append(
                    f"{student.registration_number}: enter both marks."
                )
                continue

            try:
                coursework = Decimal(cw_raw)
                examination = Decimal(exam_raw)
            except InvalidOperation:
                errors.append(
                    f"{student.registration_number}: invalid mark."
                )
                continue

            if not coursework.is_finite() or not examination.is_finite():
                errors.append(
                    f"{student.registration_number}: invalid mark."
                )
                continue

            if not Decimal("0") <= coursework <= Decimal("40"):
                errors.append(
                    f"{student.registration_number}: coursework must be 0–40."
                )
                continue

            if not Decimal("0") <= examination <= Decimal("60"):
                errors.append(
                    f"{student.registration_number}: examination must be 0–60."
                )
                continue

            if (
                course.campus_id
                and student.campus_id
                and course.campus_id != student.campus_id
            ):
                errors.append(
                    f"{student.registration_number}: student and course "
                    "belong to different campuses."
                )
                continue

            entries.append((student, coursework, examination))

        if errors:
            for error in errors:
                messages.error(request, error)
        elif not entries:
            messages.warning(request, "No marks were entered.")
        else:
            try:
                with transaction.atomic():
                    for student, coursework, examination in entries:
                        result, created = StudentResult.objects.select_for_update().get_or_create(
                            student=student,
                            course=course,
                            academic_year=academic_year,
                            semester=course.semester,
                            defaults={
                                "coursework_marks": coursework,
                                "examination_marks": examination,
                                "entered_by": request.user,
                            },
                        )

                        if created:
                            result.full_clean()
                            result.save()
                            write_audit(
                                result,
                                request.user,
                                ResultAuditLog.Action.CREATED,
                                details={
                                    "coursework": str(coursework),
                                    "examination": str(examination),
                                },
                            )
                            continue

                        if not created:
                            if result.status not in (
                                StudentResult.Status.DRAFT,
                                StudentResult.Status.REJECTED,
                            ):
                                raise ValidationError(
                                    f"{student.registration_number} has a "
                                    f"{result.get_status_display()} result. "
                                    "It cannot be edited at this stage."
                                )

                            old_values = {
                                "coursework": str(result.coursework_marks),
                                "examination": str(result.examination_marks),
                            }

                            result.coursework_marks = coursework
                            result.examination_marks = examination
                            result.entered_by = request.user
                            result.status = StudentResult.Status.DRAFT
                            result.rejection_reason = ""
                            result.submitted_by = None
                            result.submitted_at = None
                            result.full_clean()
                            result.save()

                            write_audit(
                                result,
                                request.user,
                                ResultAuditLog.Action.UPDATED,
                                details={
                                    "before": old_values,
                                    "after": {
                                        "coursework": str(coursework),
                                        "examination": str(examination),
                                    },
                                },
                                reason="Draft result updated.",
                            )
                messages.success(
                    request,
                    f"Marks saved successfully for {len(entries)} student(s)."
                )
                return redirect(
                    f"/results/course/{course.id}/?academic_year={academic_year}"
                )

            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))

    rows = []

    for enrollment in enrollments:
        result = existing_results.get(enrollment.student_id)
        rows.append({
            "student": enrollment.student,
            "result": result,
        })

    return render(request, "results/course_marks.html", {
        "course": course,
        "rows": rows,
        "academic_year": academic_year,
    })


@login_required
@require_POST
def submit_course_results(request, course_id):
    if request.user.role not in (
        User.Roles.ADMINISTRATOR,
        User.Roles.LECTURER,
    ) and not request.user.is_superuser:
        raise PermissionDenied

    course = get_accessible_course(request.user, course_id)
    academic_year = request.POST.get("academic_year", "").strip()

    if not academic_year:
        messages.error(request, "Academic year is required.")
        return redirect("results:course_marks", course_id=course.id)

    with transaction.atomic():
        enrollments = CourseEnrollment.objects.filter(
            course=course,
            is_active=True,
            student__status=Student.Status.ACTIVE,
        )

        enrolled_ids = list(
            enrollments.values_list("student_id", flat=True)
        )

        results = list(
            StudentResult.objects.select_for_update().filter(
                course=course,
                academic_year=academic_year,
                semester=course.semester,
                student_id__in=enrolled_ids,
            )
        )

        result_student_ids = {result.student_id for result in results}
        missing = set(enrolled_ids) - result_student_ids

        if missing:
            messages.error(
                request,
                f"Cannot submit: {len(missing)} actively enrolled "
                "student(s) still have no result."
            )
            return redirect(
                f"/results/course/{course.id}/?academic_year={academic_year}"
            )

        if not results:
            messages.error(request, "There are no results to submit.")
            return redirect("results:course_marks", course_id=course.id)

        if any(
            result.status not in (
                StudentResult.Status.DRAFT,
                StudentResult.Status.REJECTED,
            )
            for result in results
        ):
            messages.error(
                request,
                "Some results are already submitted, approved or published."
            )
            return redirect(
                f"/results/course/{course.id}/?academic_year={academic_year}"
            )

        for result in results:
            result.status = StudentResult.Status.SUBMITTED
            result.submitted_by = request.user
            result.submitted_at = timezone.now()
            result.rejection_reason = ""
            result.save()

            write_audit(
                result,
                request.user,
                ResultAuditLog.Action.SUBMITTED,
            )

    messages.success(request, "Course results submitted for approval.")

    if request.user.role == User.Roles.LECTURER:
        query_string = urlencode({"academic_year": academic_year})
        return redirect(
            f"/results/course/{course.id}/?{query_string}"
        )

    return redirect("results:review_results")


@login_required
def review_results(request):
    require_admin(request.user)

    base_results = StudentResult.objects.select_related(
        "student", "student__user", "course",
        "course__campus", "submitted_by", "approved_by"
    )

    if not is_central_admin(request.user):
        base_results = base_results.filter(
            course__campus_id=request.user.campus_id
        )

    submitted_results = base_results.filter(
        status=StudentResult.Status.SUBMITTED
    )

    approved_results = base_results.filter(
        status=StudentResult.Status.APPROVED,
        is_published=False,
    )

    return render(request, "results/review_results.html", {
        "results": submitted_results,
        "approved_results": approved_results,
        "is_central_admin": is_central_admin(request.user),
    })

@login_required
@require_POST
def approve_result(request, result_id):
    require_admin(request.user)

    results = StudentResult.objects.select_related(
        "course", "student"
    )

    if not is_central_admin(request.user):
        results = results.filter(course__campus_id=request.user.campus_id)

    with transaction.atomic():
        result = get_object_or_404(
            results.select_for_update(),
            pk=result_id,
            status=StudentResult.Status.SUBMITTED,
        )

        result.status = StudentResult.Status.APPROVED
        result.approved_by = request.user
        result.approved_at = timezone.now()
        result.approval_comment = request.POST.get(
            "approval_comment", ""
        ).strip()
        result.save()

        write_audit(
            result,
            request.user,
            ResultAuditLog.Action.APPROVED,
            reason=result.approval_comment,
        )

    messages.success(request, "Result approved. It is not yet published.")
    return redirect("results:review_results")


@login_required
@require_POST
def reject_result(request, result_id):
    require_admin(request.user)

    reason = request.POST.get("rejection_reason", "").strip()

    if not reason:
        messages.error(request, "A rejection reason is required.")
        return redirect("results:review_results")

    results = StudentResult.objects.select_related(
        "course", "student"
    )

    if not is_central_admin(request.user):
        results = results.filter(course__campus_id=request.user.campus_id)

    with transaction.atomic():
        result = get_object_or_404(
            results.select_for_update(),
            pk=result_id,
            status=StudentResult.Status.SUBMITTED,
        )

        result.status = StudentResult.Status.REJECTED
        result.rejection_reason = reason
        result.approved_by = None
        result.approved_at = None
        result.save()

        write_audit(
            result,
            request.user,
            ResultAuditLog.Action.REJECTED,
            reason=reason,
        )

    messages.success(request, "Result returned for correction.")
    return redirect("results:review_results")


@login_required
@require_POST
def publish_result(request, result_id):
    require_admin(request.user)

    results = StudentResult.objects.select_related(
        "course", "student"
    )

    if not is_central_admin(request.user):
        results = results.filter(course__campus_id=request.user.campus_id)

    with transaction.atomic():
        result = get_object_or_404(
            results.select_for_update(),
            pk=result_id,
            status=StudentResult.Status.APPROVED,
            is_published=False,
        )

        result.status = StudentResult.Status.PUBLISHED
        result.is_published = True
        result.published_by = request.user
        result.published_at = timezone.now()
        result.save()

        write_audit(
            result,
            request.user,
            ResultAuditLog.Action.PUBLISHED,
        )

    messages.success(request, "Approved result published to the student.")
    return redirect("results:review_results")


@login_required
def student_results(request):
    if request.user.role != User.Roles.STUDENT:
        return HttpResponseForbidden("Students only.")

    student = get_object_or_404(
        Student,
        user=request.user,
        status=Student.Status.ACTIVE,
    )

    results = StudentResult.objects.filter(
        student=student,
        status=StudentResult.Status.PUBLISHED,
        is_published=True,
    ).select_related("course").order_by(
        "-academic_year", "semester", "course__course_code"
    )

    return render(request, "results/student_results.html", {
        "student": student,
        "results": results,
    })



