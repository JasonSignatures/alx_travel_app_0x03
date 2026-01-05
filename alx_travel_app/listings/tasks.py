# listings/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import Payment

@shared_task
def send_payment_confirmation_email(payment_id):
    try:
        payment = Payment.objects.get(pk=payment_id)
    except Payment.DoesNotExist:
        return False

    if payment.status != Payment.STATUS_COMPLETED:
        return False

    subject = f"Payment confirmation - {payment.tx_ref}"
    message = render_to_string("emails/payment_confirmation.txt", {"payment": payment})
    recipient = [payment.customer_email] if payment.customer_email else []

    if not recipient:
        return False

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient,
        fail_silently=False,
    )
    return True
