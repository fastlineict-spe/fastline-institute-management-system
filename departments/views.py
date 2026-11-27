from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from accounts.models import Campus
from .models import Department


def administrator_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_active or not (
            user.is_superuser
            or getattr(user, "role", "") == "ADMINISTRATOR"
        ):
            messages.error(request, "Administrator access is required.")
            return redirect("dashboard:home")

        return view_func(request, *args, **kwargs)

    return wrapper


def get_department_campus(request):
    user = request.user
    is_central = getattr(user, "is_central_admin", False)

    campus_code = (
        request.POST.get("campus_code")
        or request.GET.get("campus")
    )

    if is_central:
        if not campus_code:
            messages.info(request, "Select a campus to manage its departments.")
            return None

        campus = Campus.objects.filter(
            code__iexact=campus_code,
            is_active=True
        ).first()

        if campus is None:
            raise PermissionDenied("The selected campus is unavailable.")

        return campus

    if not user.campus_id:
        raise PermissionDenied("Your account is not assigned to a campus.")

    campus = Campus.objects.filter(
        pk=user.campus_id,
        is_active=True
    ).first()

    if campus is None:
        raise PermissionDenied("Your assigned campus is unavailable.")

    if campus_code and campus.code.lower() != campus_code.lower():
        raise PermissionDenied("You cannot access another campus.")

    return campus


def department_list_url(campus):
    query = urlencode({"campus": campus.code})
    return f"{reverse('departments:list')}?{query}"


@administrator_required
def department_list(request):
    campus = get_department_campus(request)

    if campus is None:
        return redirect("dashboard:administrator")

    departments = Department.objects.filter(campus=campus)
    query = request.GET.get("q", "").strip()

    if query:
        departments = departments.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )

    return render(request, "departments/list.html", {
        "departments": departments,
        "query": query,
        "campus": campus,
        "total_departments": Department.objects.filter(
            campus=campus
        ).count(),
    })


@administrator_required
def department_create(request):
    campus = get_department_campus(request)

    if campus is None:
        return redirect("dashboard:administrator")

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not code or not name:
            messages.error(request, "Department code and name are required.")

        elif Department.objects.filter(
            campus=campus, code__iexact=code
        ).exists():
            messages.error(request, "That department code already exists.")

        elif Department.objects.filter(
            campus=campus, name__iexact=name
        ).exists():
            messages.error(request, "That department name already exists.")

        else:
            Department.objects.create(
                campus=campus,
                code=code,
                name=name,
                description=description,
            )
            messages.success(request, "Department registered successfully.")
            return redirect(department_list_url(campus))

    return render(request, "departments/form.html", {
        "page_title": "Register Department",
        "campus": campus,
    })


@administrator_required
def department_edit(request, department_id):
    campus = get_department_campus(request)

    if campus is None:
        return redirect("dashboard:administrator")

    department = get_object_or_404(
        Department,
        pk=department_id,
        campus=campus
    )

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()

        if not code or not name:
            messages.error(request, "Department code and name are required.")

        elif Department.objects.filter(
            campus=campus, code__iexact=code
        ).exclude(pk=department.pk).exists():
            messages.error(request, "That department code already exists.")

        elif Department.objects.filter(
            campus=campus, name__iexact=name
        ).exclude(pk=department.pk).exists():
            messages.error(request, "That department name already exists.")

        else:
            department.code = code
            department.name = name
            department.description = description
            department.save()

            messages.success(request, "Department updated successfully.")
            return redirect(department_list_url(campus))

    return render(request, "departments/form.html", {
        "page_title": "Edit Department",
        "department": department,
        "campus": campus,
    })


@administrator_required
def department_toggle(request, department_id):
    campus = get_department_campus(request)

    if campus is None:
        return redirect("dashboard:administrator")

    department = get_object_or_404(
        Department,
        pk=department_id,
        campus=campus
    )

    if request.method == "POST":
        department.is_active = not department.is_active
        department.save(update_fields=["is_active"])

        messages.success(
            request,
            "Department status updated successfully."
        )

    return redirect(department_list_url(campus))


@administrator_required
def department_delete(request, department_id):
    campus = get_department_campus(request)

    if campus is None:
        return redirect("dashboard:administrator")

    department = get_object_or_404(
        Department,
        pk=department_id,
        campus=campus
    )

    if request.method == "POST":
        from courses.models import Course

        linked_courses = Course.objects.filter(
            campus=campus,
            department__iexact=department.name
        )

        if linked_courses.exists():
            messages.error(
                request,
                "Deletion blocked: courses are assigned to this department. "
                "Reassign those courses before deleting it."
            )
        else:
            department.delete()
            messages.success(request, "Department deleted successfully.")

    return redirect(department_list_url(campus))

