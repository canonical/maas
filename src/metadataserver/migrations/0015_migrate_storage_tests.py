from django.db import migrations, models


def run_migration(apps, schema_editor):
    ScriptResult = apps.get_model("metadataserver", "ScriptResult")
    PhysicalBlockDevice = apps.get_model("maasserver", "PhysicalBlockDevice")
    # Previously ScriptResults were not assoicated with PhysicalBlockDevice as
    # one test ran on all hardware. In 2.3 each storage device has its own
    # ScriptResult. To properly show this in the UI make copies of each old
    # result for all know storage devices.
    for old_script_result in ScriptResult.objects.filter(
        physical_blockdevice=None,
        script_name__in=[
            "smartctl-validate",
            "smartctl-short",
            "smartctl-long",
            "smartctl-conveyance",
            "badblocks",
            "badblocks-destructive",
        ],
    ):
        for bd in PhysicalBlockDevice.objects.filter(
            node=old_script_result.script_set.node
        ):
            script_result = ScriptResult()
            for field in ScriptResult._meta.fields:
                if field.name == "id":
                    continue
                setattr(
                    script_result,
                    field.name,
                    getattr(old_script_result, field.name),
                )
            script_result.physical_blockdevice = bd
            script_result.save()
        old_script_result.delete()


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0014_rename_dhcp_unconfigured_ifaces")]

    operations = [migrations.RunPython(run_migration)]
