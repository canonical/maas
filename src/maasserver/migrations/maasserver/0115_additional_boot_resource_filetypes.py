from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0114_node_dynamic_to_creation_type")]

    operations = [
        migrations.AlterField(
            model_name="bootresourcefile",
            name="filetype",
            field=models.CharField(
                editable=False,
                max_length=20,
                default="root-tgz",
                choices=[
                    ("root-tgz", "Root Image (tar.gz)"),
                    ("root-dd", "Root Compressed DD (dd -> tar.gz)"),
                    ("root-dd", "Root Compressed DD (dd -> tar.gz)"),
                    (
                        "root-dd.tar",
                        "Root Tarfile with DD (dd -> root-dd.tar)",
                    ),
                    ("root-dd.raw", "Raw root DD image(dd -> root-dd.raw)"),
                    (
                        "root-dd.tar.bz2",
                        "Root Compressed DD (dd -> root-dd.tar.bz2)",
                    ),
                    (
                        "root-dd.tar.xz",
                        "Root Compressed DD (dd -> root-dd.tar.xz)",
                    ),
                    ("root-dd.bz2", "Root Compressed DD (root-dd.bz2)"),
                    ("root-dd.gz", "Root Compressed DD (root-dd.gz)"),
                    ("root-dd.xz", "Root Compressed DD (root-dd.xz)"),
                    ("root-image.gz", "Compressed Root Image"),
                    ("squashfs", "SquashFS Root Image"),
                    ("boot-kernel", "Linux ISCSI Kernel"),
                    ("boot-initrd", "Initial ISCSI Ramdisk"),
                    ("boot-dtb", "ISCSI Device Tree Blob"),
                    ("bootloader", "Bootloader"),
                    ("archive.tar.xz", "Archives.tar.xz set of files"),
                ],
            ),
        )
    ]
