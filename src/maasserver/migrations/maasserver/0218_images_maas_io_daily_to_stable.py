from django.db import migrations, models


def daily_to_stable(apps, schema_editor):
    BootSource = apps.get_model("maasserver", "BootSource")
    BootSource.objects.filter(
        models.Q(url__contains="images.maas.io")
        | models.Q(url__contains="maas.ubuntu.com")
    ).update(url="http://images.maas.io/ephemeral-v3/stable/")


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0217_notification_dismissal_timestamp")]

    operations = [migrations.RunPython(daily_to_stable)]
