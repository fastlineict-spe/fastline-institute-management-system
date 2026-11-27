from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LiveClassroomForm
from .models import LiveClassroom


def administrator_required(user):
    return user.is_authenticated and user.is_active and (
        user.is_superuser or user.role == "ADMINISTRATOR"
    )


def get_accessible_classrooms(user):
    classrooms = LiveClassroom.objects.select_related(
        "course", "course__lecturer", "created_by"
    )

    if user.is_central_admin or user.is_superuser:
        return classrooms

    if user.campus_id is None:
        raise PermissionDenied

    return classrooms.filter(
        course__lecturer__campus_id=user.campus_id
    )


@login_required
def classroom_list(request):
    if not administrator_required(request.user):
        raise PermissionDenied

    classrooms = get_accessible_classrooms(request.user).order_by(
        "-start_time"
    )

    context = {
        "classrooms": classrooms,
        "scheduled_count": classrooms.filter(
            status=LiveClassroom.Status.SCHEDULED
        ).count(),
        "completed_count": classrooms.filter(
            status=LiveClassroom.Status.COMPLETED
        ).count(),
        "cancelled_count": classrooms.filter(
            status=LiveClassroom.Status.CANCELLED
        ).count(),
        "now": timezone.now(),
    }

    return render(
        request,
        "live_classrooms/admin_list.html",
        context
    )


@login_required
def classroom_create(request):
    if not administrator_required(request.user):
        raise PermissionDenied

    form = LiveClassroomForm(
        request.POST or None,
        user=request.user
    )

    if request.method == "POST" and form.is_valid():
        classroom = form.save(commit=False)
        classroom.created_by = request.user
        classroom.save()
        return redirect("live_classrooms:admin_list")

    return render(request, "live_classrooms/form.html", {
        "form": form,
        "page_title": "Schedule Live Classroom",
        "button_text": "Schedule Classroom",
    })


@login_required
def classroom_edit(request, classroom_id):
    if not administrator_required(request.user):
        raise PermissionDenied

    classroom = get_object_or_404(
        get_accessible_classrooms(request.user),
        pk=classroom_id
    )

    form = LiveClassroomForm(
        request.POST or None,
        instance=classroom,
        user=request.user
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("live_classrooms:admin_list")

    return render(request, "live_classrooms/form.html", {
        "form": form,
        "page_title": "Edit Live Classroom",
        "button_text": "Save Changes",
    })


@login_required
def classroom_cancel(request, classroom_id):
    if not administrator_required(request.user):
        raise PermissionDenied

    if request.method == "POST":
        classroom = get_object_or_404(
            get_accessible_classrooms(request.user),
            pk=classroom_id
        )

        if classroom.status == LiveClassroom.Status.SCHEDULED:
            classroom.status = LiveClassroom.Status.CANCELLED
            classroom.save(update_fields=["status", "date_updated"])

    return redirect("live_classrooms:admin_list")


@login_required
def classroom_delete(request, classroom_id):
    if not administrator_required(request.user):
        raise PermissionDenied

    classroom = get_object_or_404(
        get_accessible_classrooms(request.user),
        pk=classroom_id
    )

    if request.method == "POST":
        classroom.delete()
        return redirect("live_classrooms:admin_list")

    return render(
        request,
        "live_classrooms/delete_confirm.html",
        {"classroom": classroom},
    )
