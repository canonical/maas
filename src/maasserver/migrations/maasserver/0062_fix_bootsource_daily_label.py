from django.db import migrations, models


def fix_bootsource_daily_label(apps, schema_editor):
    BootSource = apps.get_model("maasserver", "BootSource")
    for source in BootSource.objects.filter(
        url="http://images.maas.io/ephemeral-v2/daily/"
    ):
        for selection in source.bootsourceselection_set.filter(
            labels__contains=["release"]
        ):
            selection.labels = ["*"]
            selection.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0061_maas_nodegroup_worker_to_maas")]

    operations = [migrations.RunPython(fix_bootsource_daily_label)]
