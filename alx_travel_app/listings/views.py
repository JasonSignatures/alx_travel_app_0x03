import os
import uuid
import logging
import requests
from django.shortcuts import render
from rest_framework import viewsets
from .models import Listing, Booking, Payment
from .serializers import ListingSerializer, BookingSerializer, PaymentSerializer

from django.shortcuts import get_object_or_404
from django.conf import settings
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

logger = logging.getLogger(__name__)

CHAPA_INIT_URL = "https://api.chapa.co/v1/transaction/initialize"
CHAPA_VERIFY_URL = "https://api.chapa.co/v1/transaction/verify/{}"

CHAPA_SECRET_KEY = getattr(settings, "CHAPA_SECRET_KEY", os.environ.get("CHAPA_SECRET_KEY"))

def _headers():
    return {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }


class InitializePaymentAPIView(APIView):
    permission_classes = [permissions.AllowAny]  # adjust as needed

    def post(self, request):
        """
        Start a Chapa transaction, store Payment with status Pending, and return checkout_url.
        Expected payload: { "booking_id": <int> } or { "booking_reference": "..." , "amount": 1000, "currency":"ETB", "customer_email":"..." }
        """
        data = request.data
        # Prefer explicit amount provided otherwise use booking.price (adjust to your Booking model)
        amount = data.get("amount")
        currency = data.get("currency", "ETB")
        booking_id = data.get("booking_id")
        booking_reference = data.get("booking_reference")

        # Resolve booking if booking_id provided
        booking = None
        if booking_id:
            booking = get_object_or_404(Booking, id=booking_id)
            # assume booking has price field (adjust to your model)
            if not amount:
                amount = getattr(booking, "price", None)

        if amount is None:
            return Response({"detail": "amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        # customer info for receipt
        customer_email = data.get("customer_email") or (booking.customer.email if booking and getattr(booking, "customer", None) else None)
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")

        # generate unique tx_ref
        tx_ref = data.get("tx_ref") or f"booking-{uuid.uuid4().hex[:12]}"

        # Build callback and return URLs - ensure they are reachable (ngrok for local testing)
        # return_url is optional - where Chapa will redirect user after payment
        return_url = data.get("return_url") or request.build_absolute_uri(reverse("payments:chapa_return"))
        callback_url = data.get("callback_url") or request.build_absolute_uri(reverse("payments:chapa_callback"))

        # prepare payload for Chapa
        payload = {
            "amount": int(float(amount)),   # Chapa expects integer digits (e.g., for ETB)
            "currency": currency,
            "first_name": first_name,
            "last_name": last_name,
            "email": customer_email,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            # optional customization: "customization": {...}
        }

        # call Chapa
        try:
            r = requests.post(CHAPA_INIT_URL, json=payload, headers=_headers(), timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            logger.exception("Failed to initialize chapa payment: %s", exc)
            return Response({"detail": "Failed to initialize payment", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        resp_json = r.json()
        # expected success structure: resp_json['status'] == 'success' and resp_json['data']['checkout_url']
        if not resp_json.get("status") in ("success", True):
            logger.error("Chapa init error: %s", resp_json)
            return Response({"detail": "Chapa returned an error", "response": resp_json}, status=status.HTTP_400_BAD_REQUEST)

        data_obj = resp_json.get("data", {})
        checkout_url = data_obj.get("checkout_url")
        chapa_ref = data_obj.get("ref_id") or data_obj.get("ref")

        # Save Payment record
        payment = Payment.objects.create(
            booking=booking,
            booking_reference=booking_reference,
            amount=amount,
            currency=currency,
            tx_ref=tx_ref,
            chapa_ref=chapa_ref,
            chapa_checkout_url=checkout_url,
            status=Payment.STATUS_PENDING,
            customer_email=customer_email,
            customer_first_name=first_name,
            customer_last_name=last_name
        )

        serialized = PaymentSerializer(payment)
        return Response({
            "payment": serialized.data,
            "checkout_url": checkout_url
        }, status=status.HTTP_201_CREATED)


class VerifyPaymentAPIView(APIView):
    permission_classes = [permissions.AllowAny]  # change to IsAuthenticated if needed

    def get(self, request, tx_ref):
        """
        Verify transaction with Chapa using tx_ref and update Payment.
        """
        try:
            r = requests.get(CHAPA_VERIFY_URL.format(tx_ref), headers=_headers(), timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            logger.exception("Chapa verify request failed: %s", exc)
            return Response({"detail": "Failed to verify payment", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        resp_json = r.json()
        # Example response contains resp_json['status'] and resp_json['data']['status']
        chapa_data = resp_json.get("data", {}) or {}
        chapa_status = chapa_data.get("status")
        chapa_ref = chapa_data.get("ref_id") or chapa_data.get("ref")
        amount = chapa_data.get("amount")

        # find the Payment record
        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found for tx_ref"}, status=status.HTTP_404_NOT_FOUND)

        # Update Payment.status
        if chapa_status in ("success", "completed", "Success"):
            payment.status = Payment.STATUS_COMPLETED
            payment.chapa_ref = chapa_ref or payment.chapa_ref
            payment.save()
            # optional: trigger email asynchronously (Celery task)
            from .tasks import send_payment_confirmation_email
            send_payment_confirmation_email.delay(payment.id)
        else:
            payment.status = Payment.STATUS_FAILED
            payment.chapa_ref = chapa_ref or payment.chapa_ref
            payment.save()

        return Response({
            "tx_ref": tx_ref,
            "chapa_status": chapa_status,
            "payment_status": payment.status,
            "raw": resp_json
        }, status=status.HTTP_200_OK)


class ChapaCallbackView(APIView):
    """
    Endpoint to receive Chapa callback / return. Chapa will call callback_url with:
    { "trx_ref": "...", "ref_id": "...", "status": "success" } (as GET).
    We verify with Chapa and update records (safer than trusting callback payload).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        trx_ref = request.GET.get("trx_ref") or request.GET.get("tx_ref") or request.GET.get("trx_ref")
        ref_id = request.GET.get("ref_id")
        status_param = request.GET.get("status")

        if not trx_ref:
            return Response({"detail": "trx_ref (tx_ref) is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Call verify endpoint to get authoritative status
        verify_view = VerifyPaymentAPIView()
        return verify_view.get(request, tx_ref=trx_ref)
