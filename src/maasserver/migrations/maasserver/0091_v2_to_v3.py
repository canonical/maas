from django.db import migrations, models


def v2_to_v3(apps, schema_editor):
    BootSource = apps.get_model("maasserver", "BootSource")
    for source in BootSource.objects.all():
        if (
            "images.maas.io/ephemeral-v2" in source.url
            or "maas.ubuntu.com/images/ephemeral-v2" in source.url
        ):
            source.url = "http://images.maas.io/ephemeral-v3/daily/"
            source.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0090_bootloaders")]

    operations = [migrations.RunPython(v2_to_v3)]
