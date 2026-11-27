from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("send/", views.send_message, name="send_message"),
    path("conversation/<int:message_id>/", views.conversation, name="conversation"),
    path("delete/<int:message_id>/", views.delete_message, name="delete_message"),
]