from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone
from students.models import Student
from accounts.models import Campus
from .models import Payment, StudentFeeCharge
import uuid


@login_required
def payment_record(request):
    user = request.user
    central = user.is_superuser or getattr(user, "is_central_admin", False)

    if not user.is_active or not (
        user.is_superuser or user.role == "ADMINISTRATOR"
    ):
        raise PermissionDenied("Only authorised administrators can record payments.")

    campuses = Campus.objects.filter(is_active=True)

    if central:
        campus_id = request.POST.get("campus") or request.GET.get("campus")
        campus = campuses.filter(pk=campus_id).first() if campus_id else campuses.first()
    else:
        campus = campuses.filter(pk=user.campus_id).first()

    if not campus:
        raise PermissionDenied("No authorised campus is available.")

    students = list(
        Student.objects.filter(
            campus=campus,
            status=Student.Status.ACTIVE
        ).select_related("user", "campus").order_by(
            "user__first_name", "user__last_name"
        )
    )

    student_rows = []
    balances = {}

    for student in students:
        charges = StudentFeeCharge.objects.filter(
            student=student
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        payments = Payment.objects.filter(
            student=student
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        balance = charges - payments
        balances[student.pk] = balance

        student_rows.append({
            "student": student,
            "balance": balance,
        })

    if request.method == "POST":
        student = next(
            (s for s in students if str(s.pk) == request.POST.get("student")),
            None
        )

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except Exception:
            amount = Decimal("0")

        method = request.POST.get("method", "")
        reference = request.POST.get("transaction_reference", "").strip()

        if not student:
            messages.error(request, "Select a valid active student.")
        elif amount <= 0:
            messages.error(request, "Enter a valid payment amount.")
        elif method not in Payment.Method.values:
            messages.error(request, "Select a valid payment method.")
        elif balances.get(student.pk, Decimal("0")) <= 0:
            messages.error(request, "No outstanding fee charge. Assign fees first.")
        elif amount > balances[student.pk]:
            messages.error(request, "Payment exceeds the outstanding balance.")
        elif reference and Payment.objects.filter(
            campus=campus,
            method=method,
            transaction_reference=reference
        ).exists():
            messages.error(request, "This transaction reference has already been recorded.")
        else:
            with transaction.atomic():
                payment = Payment.objects.create(
                    student=student,
                    campus=campus,
                    amount=amount,
                    method=method,
                    receipt_number=(
                        f"FIMS-{timezone.now():%Y%m%d}-"
                        f"{uuid.uuid4().hex[:8].upper()}"
                    ),
                    transaction_reference=reference,
                    received_by=user,
                )

            messages.success(
                request,
                f"Payment recorded successfully. Receipt: {payment.receipt_number}"
            )
            return redirect("finance:payment_record")

    return render(request, "finance/payment_record.html", {
        "campus": campus,
        "campuses": campuses,
        "student_rows": student_rows,
        "central": central,
    })

@login_required
def payment_receipt(request, payment_id):
    from django.shortcuts import get_object_or_404
    from django.db.models import Sum
    from decimal import Decimal
    import base64
    from io import BytesIO

    user = request.user
    central = user.is_superuser or getattr(user, "is_central_admin", False)

    if not user.is_active or not (
        user.is_superuser or user.role == "ADMINISTRATOR"
    ):
        raise PermissionDenied("You are not authorised to view financial receipts.")

    payments = Payment.objects.select_related(
        "student__user", "campus", "received_by"
    )

    if not central:
        payments = payments.filter(campus_id=user.campus_id)

    payment = get_object_or_404(payments, pk=payment_id)

    charges = StudentFeeCharge.objects.filter(
        student=payment.student
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    paid = Payment.objects.filter(
        student=payment.student
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    balance = charges - paid

    qr_code = None
    try:
        import qrcode
        from django.urls import reverse
        qr_data = request.build_absolute_uri(reverse("finance:payment_verify", args=[payment.verification_token]))
        qr = qrcode.make(qr_data)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qr_code = base64.b64encode(buffer.getvalue()).decode("ascii")
    except ImportError:
        pass

    return render(request, "finance/payment_receipt.html", {
        "payment": payment,
        "charges": charges,
        "paid": paid,
        "balance": balance,
        "qr_code": qr_code,
    })


def payment_verify(request, token):
    """Public page for checking whether a FIMS payment receipt exists."""
    from django.shortcuts import render
    from .models import Payment

    payment = Payment.objects.select_related(
        "student__user", "campus"
    ).filter(verification_token=token).first()

    return render(request, "finance/payment_verify.html", {
        "payment": payment,
        "verified": payment is not None,
    })
