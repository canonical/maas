from django.db import migrations


def drop_ipaddr_scripts(apps, schema_editor):
    Script = apps.get_model("metadataserver", "Script")
    Script.objects.filter(name="40-maas-01-network-interfaces").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0025_nodedevice"),
    ]

    operations = [migrations.RunPython(drop_ipaddr_scripts)]
