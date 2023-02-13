from django.db import migrations, models


def amt_remove_mac_address(apps, schema_editor):
    BMC = apps.get_model("maasserver", "BMC")
    for bmc in BMC.objects.filter(power_type="amt"):
        bmc.power_parameters.pop("mac_address", "")
        bmc.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0059_merge")]

    operations = [migrations.RunPython(amt_remove_mac_address)]
