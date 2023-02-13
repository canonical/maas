from django.db import migrations


def reorder_machine_resources_script(apps, schema_editor):
    ScriptResult = apps.get_model("metadataserver", "ScriptResult")
    old_scripts = ScriptResult.objects.filter(
        script_name="40-maas-01-machine-resources"
    )
    old_scripts.update(script_name="20-maas-03-machine-resources")


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0026_drop_ipaddr_script")]

    operations = [migrations.RunPython(reorder_machine_resources_script)]
