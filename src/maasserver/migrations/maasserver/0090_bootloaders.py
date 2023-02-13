from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0089_active_discovery")]

    operations = [
        migrations.AddField(
            model_name="bootresource",
            name="bootloader_type",
            field=models.CharField(max_length=32, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="bootsourcecache",
            name="bootloader_type",
            field=models.CharField(max_length=32, null=True, blank=True),
        ),
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
                    ("squashfs", "SquashFS Root Image"),
                    ("boot-kernel", "Linux ISCSI Kernel"),
                    ("boot-initrd", "Initial ISCSI Ramdisk"),
                    ("boot-dtb", "ISCSI Device Tree Blob"),
                    ("bootloader", "Bootloader"),
                    ("archive.tar.xz", "Archives.tar.xz set of files"),
                ],
                editable=False,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="bootresourcefile",
            unique_together={("resource_set", "filename")},
        ),
    ]
