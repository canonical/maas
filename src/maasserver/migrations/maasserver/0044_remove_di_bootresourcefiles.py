from django.db import migrations, models

# Previous DI file types.
DI_FILE_TYPES = ["di-kernel", "di-initrd", "di-dtb"]


def remove_di_bootresourcefiles(apps, schema_editor):
    BootResourceFile = apps.get_model("maasserver", "BootResourceFile")
    LargeFile = apps.get_model("maasserver", "LargeFile")
    for resource_file in BootResourceFile.objects.filter(
        filetype__in=DI_FILE_TYPES
    ):
        # Delete the largefile and content before deleting the resource file
        # so the post commit hooks are not called in the migration.
        try:
            largefile = resource_file.largefile
        except LargeFile.DoesNotExist:
            largefile = None
        if largefile is not None:
            if largefile.content is not None:
                largefile.content.unlink()
            largefile.delete()
        resource_file.delete()


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0043_dhcpsnippet")]

    operations = [
        migrations.RunPython(remove_di_bootresourcefiles),
        migrations.AlterField(
            model_name="bootresourcefile",
            name="filetype",
            field=models.CharField(
                max_length=20,
                default="root-tgz",
                choices=[
                    ("root-tgz", "Root Image (tar.gz)"),
                    ("root-dd", "Root Compressed DD (dd -> tar.gz)"),
                    ("root-image.gz", "Compressed Root Image"),
                    ("boot-kernel", "Linux ISCSI Kernel"),
                    ("boot-initrd", "Initial ISCSI Ramdisk"),
                    ("boot-dtb", "ISCSI Device Tree Blob"),
                ],
                editable=False,
            ),
        ),
    ]
