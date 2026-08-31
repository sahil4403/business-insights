from django.db import migrations


def convert_category_values(apps, schema_editor):
    Labour = apps.get_model('labour', 'Labour')

    # Map old codes to new merged category
    Labour.objects.filter(category__in=['LABOUR', 'TRACTOR_DRIVER']).update(category='TRACTOR')


def reverse(apps, schema_editor):
    # No reverse needed (best-effort: cannot recover original split)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("labour", "0010_alter_labour_category"),
    ]

    operations = [
        migrations.RunPython(convert_category_values, reverse),
    ]
