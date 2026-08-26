# Generated for lumpsum payment grouping (single-line display + accurate trip status)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0017_trip_linked_inward_trip"),
    ]

    operations = [
        migrations.AddField(
            model_name="trippayment",
            name="payment_group",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Shared id for all rows created from one lumpsum payment.",
                max_length=32,
                null=True,
            ),
        ),
    ]
