from django.db import migrations


def backfill_payment_dates(apps, schema_editor):
    """
    One-time fix: payments saved without a date never appeared in the
    statement/report outstanding math. Give them a sensible date:
    their trip's date if linked, otherwise the day the record was created.
    """
    TripPayment = apps.get_model('trips', 'TripPayment')

    for payment in TripPayment.objects.filter(payment_date__isnull=True):
        if payment.trip_id and payment.trip and payment.trip.trip_date:
            payment.payment_date = payment.trip.trip_date
        elif payment.created_at:
            payment.payment_date = payment.created_at.date()
        else:
            import django.utils.timezone as timezone
            payment.payment_date = timezone.localdate()
        payment.save(update_fields=['payment_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('trips', '0015_alter_trip_trip_date_alter_trippayment_payment_date'),
    ]

    operations = [
        migrations.RunPython(backfill_payment_dates, migrations.RunPython.noop),
    ]
