from django.db import migrations, models


def add_kflavor_to_boot_resource(apps, schema_editor):
    BootResource = apps.get_model("maasserver", "BootResource")
    for resource in BootResource.objects.all():
        if "kflavor" in resource.extra:
            resource.kflavor = resource.extra["kflavor"]
            del resource.extra["kflavor"]
            resource.save()


def add_kflavor_to_boot_source_cache(apps, schema_editor):
    BootSourceCache = apps.get_model("maasserver", "BootSourceCache")
    for bsc in BootSourceCache.objects.filter(os="ubuntu"):
        # The kflavor was never stored as part of the BootSourceCache
        # however previosuly we only had generic kernels in the stream.
        bsc.kflavor = "generic"
        bsc.save()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0081_allow_larger_bootsourcecache_fields")]

    operations = [
        migrations.AddField(
            model_name="bootresource",
            name="kflavor",
            field=models.CharField(max_length=32, blank=True, null=True),
        ),
        migrations.RunPython(add_kflavor_to_boot_resource),
        migrations.AddField(
            model_name="bootsourcecache",
            name="kflavor",
            field=models.CharField(max_length=32, blank=True, null=True),
        ),
        migrations.RunPython(add_kflavor_to_boot_source_cache),
    ]
