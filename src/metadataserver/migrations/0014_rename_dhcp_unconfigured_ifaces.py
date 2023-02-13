from django.db import migrations, models


def rename_dhcp_unconfigured_ifaces(apps, schema_editor):
    # Fixes LP: 1727551
    ScriptResult = apps.get_model("metadataserver", "ScriptResult")
    for script_result in ScriptResult.objects.filter(
        script_name="00-maas-06-dhcp-unconfigured-ifaces"
    ):
        script_result.script_name = "00-maas-05-dhcp-unconfigured-ifaces"
        script_result.save()


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0013_scriptresult_physicalblockdevice")
    ]

    operations = [migrations.RunPython(rename_dhcp_unconfigured_ifaces)]
