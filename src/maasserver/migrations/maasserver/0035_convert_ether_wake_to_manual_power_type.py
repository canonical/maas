from django.db import migrations, models


def convert_ether_wake_to_manual_power_type(apps, schema_editor):
    BMC = apps.get_model("maasserver", "BMC")
    for bmc in BMC.objects.filter(power_type="ether_wake"):
        bmc.power_type = "manual"
        bmc.save()


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0034_rename_mount_params_as_mount_options")
    ]

    operations = [
        migrations.RunPython(convert_ether_wake_to_manual_power_type)
    ]
