"""
Vehicle document expiry engine:
- get_expiry_alerts(): dashboard banner ke liye upcoming/expired documents
- check_and_notify():  30/15/7 din pehle + expired par WhatsApp (dedupe flags se
                       har window me sirf EK baar message jaata hai)
"""

import logging

from django.utils import timezone

from .models import VehicleDocument
from .whatsapp import send_whatsapp_message

logger = logging.getLogger('trips')

WINDOWS = [
    (30, 'notified_30'),
    (15, 'notified_15'),
    (7, 'notified_7'),
]


def _fmt_date(d):
    return d.strftime('%d-%m-%Y') if d else ''


def _build_message(doc, days_left):
    if days_left < 0:
        urgency = f"❌ EXPIRE ho chuka hai ({_fmt_date(doc.expiry_date)}) — foran renew karein!"
    elif days_left == 0:
        urgency = "⏰ AAJ expire ho raha hai!"
    else:
        urgency = f"⏳ {days_left} din bache hain"

    return (
        "🚨 Shri Raj Construction — Document Alert\n"
        f"🚚 Vehicle: {doc.vehicle.registration_number}\n"
        f"📄 {doc.get_doc_type_display()}"
        + (f" (#{doc.document_number})" if doc.document_number else "") + "\n"
        f"📅 Expiry: {_fmt_date(doc.expiry_date)}\n"
        f"{urgency}\n"
        "Krpya renew karke site par update karein."
    )


def get_expiry_alerts(limit=None):
    """
    Dashboard banner ke liye — expired + 30 din ke andar wale documents,
    urgent (kam din bache) pehle.
    """
    today = timezone.localdate()
    docs = (
        VehicleDocument.objects
        .select_related('vehicle')
        .filter(expiry_date__lte=today + timezone.timedelta(days=30))
        .order_by('expiry_date')
    )
    alerts = []
    for doc in docs:
        alerts.append({
            'id': doc.id,
            'vehicle': doc.vehicle.registration_number,
            'vehicle_id': doc.vehicle_id,
            'doc_type': doc.get_doc_type_display(),
            'expiry_date': _fmt_date(doc.expiry_date),
            'days_left': doc.days_left,
            'urgency': doc.urgency,
        })
        if limit and len(alerts) >= limit:
            break
    return alerts


def check_and_notify():
    """
    Roz ek baar chalao (dashboard se daily-guard ke saath).
    Har document par: 30/15/7-din windows + expired — har window ka
    WhatsApp sirf pehli baar (flag set ho jaata hai).
    Returns: list of sent alert descriptions.
    """
    today = timezone.localdate()
    sent = []

    docs = VehicleDocument.objects.select_related('vehicle').all()

    for doc in docs:
        days_left = (doc.expiry_date - today).days

        # ---- Window reminders (30 / 15 / 7) ----
        for window, flag in WINDOWS:
            if 0 <= days_left <= window and not getattr(doc, flag):
                msg = _build_message(doc, days_left)
                if send_whatsapp_message(msg):
                    sent.append(f"{doc.vehicle.registration_number} {doc.get_doc_type_display()} ({days_left}d)")
                setattr(doc, flag, True)

        # ---- Expired ----
        if days_left < 0 and not doc.notified_expired:
            msg = _build_message(doc, days_left)
            if send_whatsapp_message(msg):
                sent.append(f"{doc.vehicle.registration_number} {doc.get_doc_type_display()} (EXPIRED)")
            doc.notified_expired = True

        doc.save(update_fields=['notified_30', 'notified_15', 'notified_7', 'notified_expired'])

    if sent:
        logger.info('Doc expiry notifications sent: %s', sent)
    return sent
