from django.db import migrations
import petname


def generate_bmc_names(apps, schema_editor):
    BMC = apps.get_model("maasserver", "BMC")
    generated_names = []
    for bmc in BMC.objects.all():
        while True:
            bmc.name = petname.Generate(2, "-")
            if bmc.name not in generated_names:
                bmc.save()
                generated_names.append(bmc.name)
                break


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0107_chassis_to_pods")]

    operations = [migrations.RunPython(generate_bmc_names)]
