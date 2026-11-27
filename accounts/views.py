
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied

from students.models import Student


def login_view(request):
    if request.user.is_authenticated:
        return redirect_user(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            if user.role == "STUDENT":
                try:
                    student = user.student_profile
                except Student.DoesNotExist:
                    messages.error(
                        request,
                        "Your student account is not properly registered."
                    )
                    return render(request, "accounts/login.html")

                if student.status != Student.Status.ACTIVE:
                    messages.error(
                        request,
                        "Your student account is currently inactive. "
                        "Please contact the administration office."
                    )
                    return render(request, "accounts/login.html")

            login(request, user)
            return redirect_user(user)

        messages.error(
            request,
            "Invalid admission number or password."
        )

    return render(request, "accounts/login.html")



def redirect_user(user):
    if user.is_superuser or user.role == "ADMINISTRATOR":
        return redirect("dashboard:administrator")

    if user.role == "LECTURER":
        return redirect("dashboard:lecturer")

    if user.role == "STUDENT":
        return redirect("students:dashboard")

    return redirect("accounts:login")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have successfully logged out.")
    return redirect("accounts:login")
