from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Message

User = get_user_model()


@login_required
def inbox(request):
    received = Message.objects.filter(
        recipient=request.user,
        recipient_deleted=False
    ).select_related("sender")

    sent = Message.objects.filter(
        sender=request.user,
        sender_deleted=False
    ).select_related("recipient")

    return render(request, "messaging/inbox.html", {
        "received": received,
        "sent": sent,
    })


@login_required
def send_message(request):
    if request.method == "POST":
        recipient_id = request.POST.get("recipient")
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()

        recipient = get_object_or_404(
            User, id=recipient_id, is_active=True
        )

        if recipient.role not in ["LECTURER", "ADMINISTRATOR"]:
            return HttpResponseForbidden(
                "You can only message a lecturer or administrator."
            )

        if not subject or not body:
            messages.error(request, "Please complete all message fields.")
        else:
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body
            )
            messages.success(request, "Your message has been sent.")
            return redirect("messaging:inbox")

    lecturers = User.objects.filter(
        role__in=["LECTURER", "ADMINISTRATOR"],
        is_active=True
    ).order_by("first_name", "username")

    return render(request, "messaging/send_message.html", {
        "lecturers": lecturers,
    })


@login_required
def conversation(request, message_id):
    message = get_object_or_404(
        Message.objects.select_related("sender", "recipient"),
        id=message_id
    )

    if request.user not in [message.sender, message.recipient]:
        return HttpResponseForbidden(
            "You are not authorised to view this message."
        )

    if request.method == "POST":
        body = request.POST.get("body", "").strip()

        if not body:
            messages.error(request, "Please write your reply.")
        else:
            recipient = (
                message.recipient
                if message.sender_id == request.user.id
                else message.sender
            )

            reply = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=message.subject,
                body=body
            )

            return redirect(
                "messaging:conversation",
                message_id=reply.id
            )

    if message.recipient_id == request.user.id and not message.is_read:
        message.is_read = True
        message.save(update_fields=["is_read"])

    conversation_messages = Message.objects.filter(
        Q(sender=message.sender, recipient=message.recipient) |
        Q(sender=message.recipient, recipient=message.sender),
        subject=message.subject
    ).filter(
        Q(sender=request.user, sender_deleted=False) |
        Q(recipient=request.user, recipient_deleted=False)
    ).select_related("sender", "recipient").order_by("sent_at")

    return render(request, "messaging/conversation.html", {
        "message": message,
        "conversation_messages": conversation_messages,
    })


@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)

    if message.sender_id == request.user.id:
        delete_field = "sender_deleted"
    elif message.recipient_id == request.user.id:
        delete_field = "recipient_deleted"
    else:
        return HttpResponseForbidden(
            "You are not authorised to delete this message."
        )

    if request.method == "POST":
        setattr(message, delete_field, True)

        if message.sender_deleted and message.recipient_deleted:
            message.delete()
        else:
            message.save(update_fields=[delete_field])

        messages.success(request, "Message deleted from your mailbox.")
        return redirect("messaging:inbox")

    return render(request, "messaging/confirm_delete.html", {
        "message": message,
    })