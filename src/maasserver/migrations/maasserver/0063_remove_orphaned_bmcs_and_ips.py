from django.db import migrations


# Copied from Node model.
def remove_orphaned_bmcs(apps, schema_editor):
    Node = apps.get_model("maasserver", "Node")
    BMC = apps.get_model("maasserver", "BMC")
    used_bmcs = Node.objects.values_list("bmc_id", flat=True).distinct()
    BMC.objects.exclude(id__in=used_bmcs).delete()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0062_fix_bootsource_daily_label")]

    operations = [migrations.RunPython(remove_orphaned_bmcs)]
