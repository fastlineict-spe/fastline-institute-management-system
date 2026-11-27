from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import router
from django.db.models.deletion import Collector, ProtectedError
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import Campus


def is_central_admin(user):
    return user.is_superuser or user.is_central_admin


def administrator_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_superuser or
                getattr(request.user, "role", "") == "ADMINISTRATOR"):
            messages.error(request, "Administrator access is required.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)
    return wrapper


def lecturer_queryset(request):
    User = get_user_model()
    lecturers = User.objects.filter(role="LECTURER").select_related("campus")

    if is_central_admin(request.user):
        return lecturers

    if not request.user.campus_id:
        return lecturers.none()

    return lecturers.filter(campus_id=request.user.campus_id)


def available_campuses(request):
    campuses = Campus.objects.filter(is_active=True).order_by("name")
    if is_central_admin(request.user):
        return campuses
    if request.user.campus_id:
        return campuses.filter(pk=request.user.campus_id)
    return campuses.none()


def resolve_lecturer_campus(request, submitted_campus_id):
    if is_central_admin(request.user):
        try:
            return Campus.objects.get(
                pk=submitted_campus_id,
                is_active=True
            )
        except (Campus.DoesNotExist, ValueError, TypeError):
            return None

    campus = request.user.campus
    if campus and campus.is_active:
        return campus
    return None


@administrator_required
def lecturer_list(request):
    lecturers = lecturer_queryset(request).order_by(
        "campus__name", "first_name", "last_name"
    )

    query = request.GET.get("q", "").strip()
    if query:
        lecturers = lecturers.filter(
            first_name__icontains=query
        ) | lecturers.filter(
            last_name__icontains=query
        ) | lecturers.filter(
            username__icontains=query
        ) | lecturers.filter(
            email__icontains=query
        ) | lecturers.filter(
            phone_number__icontains=query
        )

    scoped = lecturer_queryset(request)

    return render(request, "lecturers/list.html", {
        "lecturers": lecturers,
        "query": query,
        "total_lecturers": scoped.count(),
        "active_lecturers": scoped.filter(is_active=True).count(),
        "campuses": available_campuses(request),
        "is_central_admin": is_central_admin(request.user),
    })


@administrator_required
def lecturer_create(request):
    errors = []

    if request.method == "POST":
        User = get_user_model()
        data = request.POST

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        campus = resolve_lecturer_campus(
            request, data.get("campus_id", "")
        )

        if not username or not email or not data.get("first_name", "").strip():
            errors.append("First name, username and email are required.")

        if User.objects.filter(username__iexact=username).exists():
            errors.append("That username is already in use.")

        if User.objects.filter(email__iexact=email).exists():
            errors.append("That email address is already in use.")

        if password != data.get("confirm_password", ""):
            errors.append("The passwords do not match.")

        try:
            password_validation.validate_password(password)
        except ValidationError as exc:
            errors.extend(exc.messages)

        if not campus:
            errors.append("Select a valid active campus. Contact the central administrator if your campus is not assigned.")

        if not errors:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=data.get("first_name", "").strip(),
                last_name=data.get("last_name", "").strip(),
                phone_number=data.get("phone_number", "").strip(),
                role="LECTURER",
                campus=campus,
                is_active=True,
            )
            messages.success(request, "Lecturer registered successfully.")
            return redirect("lecturers:list")

        for error in errors:
            messages.error(request, error)

    return render(request, "lecturers/form.html", {
        "page_title": "Register Lecturer",
        "action_label": "Register Lecturer",
        "campuses": available_campuses(request),
        "selected_campus_id": (
            request.POST.get("campus_id", "")
            if request.method == "POST"
            else (
                request.user.campus_id
                if not is_central_admin(request.user)
                else ""
            )
        ),
        "is_central_admin": is_central_admin(request.user),
    })


@administrator_required
def lecturer_edit(request, user_id):
    lecturer = get_object_or_404(
        lecturer_queryset(request),
        pk=user_id
    )

    if request.method == "POST":
        User = get_user_model()
        data = request.POST

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        errors = []

        if not username or not email or not data.get("first_name", "").strip():
            errors.append("First name, username and email are required.")

        if User.objects.filter(
            username__iexact=username
        ).exclude(pk=lecturer.pk).exists():
            errors.append("That username is already in use.")

        if User.objects.filter(
            email__iexact=email
        ).exclude(pk=lecturer.pk).exists():
            errors.append("That email address is already in use.")

        campus = lecturer.campus

        if is_central_admin(request.user):
            campus = resolve_lecturer_campus(
                request, data.get("campus_id", "")
            )
            if not campus:
                errors.append("Select a valid active campus.")

        if not errors:
            lecturer.username = username
            lecturer.email = email
            lecturer.first_name = data.get("first_name", "").strip()
            lecturer.last_name = data.get("last_name", "").strip()
            lecturer.phone_number = data.get("phone_number", "").strip()
            lecturer.campus = campus
            lecturer.save()

            messages.success(request, "Lecturer details updated.")
            return redirect("lecturers:list")

        for error in errors:
            messages.error(request, error)

    return render(request, "lecturers/form.html", {
        "page_title": "Edit Lecturer",
        "action_label": "Save Changes",
        "lecturer": lecturer,
        "campuses": available_campuses(request),
        "selected_campus_id": (
            request.POST.get("campus_id", lecturer.campus_id)
            if request.method == "POST"
            else lecturer.campus_id
        ),
        "is_central_admin": is_central_admin(request.user),
    })


@administrator_required
def lecturer_toggle(request, user_id):
    if request.method != "POST":
        return redirect("lecturers:list")

    lecturer = get_object_or_404(
        lecturer_queryset(request),
        pk=user_id
    )

    lecturer.is_active = not lecturer.is_active
    lecturer.save(update_fields=["is_active"])

    messages.success(
        request,
        "Lecturer account activated." if lecturer.is_active
        else "Lecturer account deactivated."
    )
    return redirect("lecturers:list")


@administrator_required
def lecturer_delete(request, user_id):
    User = get_user_model()
    lecturer = get_object_or_404(
        lecturer_queryset(request),
        pk=user_id
    )

    if request.method == "POST":
        try:
            collector = Collector(using=router.db_for_write(User))
            collector.collect([lecturer])

            related_objects_exist = any(
                model is not User and bool(objects)
                for model, objects in collector.data.items()
            )
            pending_fast_deletes = any(
                qs.exists() for qs in collector.fast_deletes
            )
            pending_updates = any(
                bool(group)
                for groups in collector.field_updates.values()
                for group in groups
            )

            if related_objects_exist or pending_fast_deletes or pending_updates:
                messages.error(
                    request,
                    "Permanent deletion blocked: this lecturer has linked records "
                    "or dependent data. The account has been kept. Deactivate it "
                    "instead to preserve academic history."
                )
                return redirect("lecturers:list")

            lecturer.delete()
            messages.success(request, "Lecturer account permanently deleted.")

        except ProtectedError:
            messages.error(
                request,
                "Permanent deletion blocked because protected records are linked. "
                "No records were deleted."
            )

        return redirect("lecturers:list")

    return render(request, "lecturers/confirm_delete.html", {
        "lecturer": lecturer,
    })