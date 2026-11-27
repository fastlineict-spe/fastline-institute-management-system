from django.urls import path
from . import views
from . import safe_assignment
from . import payment_views

app_name = "finance"

urlpatterns = [
    path("fees/assign/preview/", safe_assignment.fee_assignment_preview, name="fee_assignment_preview"),
    path("fees/assign/confirm/", safe_assignment.fee_assignment_confirm, name="fee_assignment_confirm"),
    path("fees/assign/", views.fee_assignment, name="fee_assignment"),
    path("payments/record/", payment_views.payment_record, name="payment_record"),
]

urlpatterns += [path('payments/receipt/<int:payment_id>/', payment_views.payment_receipt, name='payment_receipt')]

urlpatterns += [
    path("verify/<str:token>/", payment_views.payment_verify, name="payment_verify"),
]
