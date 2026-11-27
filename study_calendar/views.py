from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden
from django.utils import timezone

from students.models import Student
from courses.models import CourseEnrollment
from assignments.models import Assignment
from .models import CalendarEvent


@login_required
def student_calendar(request):
    if request.user.role != "STUDENT":
        return HttpResponseForbidden("Students only.")

    student = get_object_or_404(
        Student, user=request.user, status="ACTIVE"
    )

    events = []

    academic_events = CalendarEvent.objects.filter(is_published=True)

    for event in academic_events:
        events.append({
            "title": event.title,
            "description": event.description,
            "date": event.start_date,
            "event_type": event.get_event_type_display(),
            "course": "",
            "url": "",
            "source": "Institute event",
        })

    enrolled_course_ids = CourseEnrollment.objects.filter(
        student=student,
        is_active=True,
        course__is_active=True
    ).values_list("course_id", flat=True)

    assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids,
        is_published=True
    ).select_related("course")

    for assignment in assignments:
        events.append({
            "title": assignment.title,
            "description": assignment.instructions,
            "date": assignment.due_date,
            "event_type": "Assignment Deadline",
            "course": assignment.course.course_code,
            "url": f"/assignments/student/{assignment.id}/",
            "source": "Course assignment",
        })

    events.sort(key=lambda item: item["date"])

    now = timezone.now()
    upcoming_events = [
        event for event in events if event["date"] >= now
    ]
    past_events = [
        event for event in events if event["date"] < now
    ]
    past_events.reverse()

    return render(request, "study_calendar/student_calendar.html", {
        "student": student,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
    })