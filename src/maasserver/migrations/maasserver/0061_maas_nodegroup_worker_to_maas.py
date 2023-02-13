from django.conf import settings
from django.db import migrations, models


def maas_nodegroup_worker_to_maas(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    for user in User.objects.filter(username="maas-nodegroup-worker"):
        user.username = "MAAS"
        user.first_name = "MAAS"
        user.email = "maas@localhost"
        user.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0060_amt_remove_mac_address")]

    operations = [migrations.RunPython(maas_nodegroup_worker_to_maas)]
