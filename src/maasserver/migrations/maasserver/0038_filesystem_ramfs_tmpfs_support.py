from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0037_node_last_image_sync")]

    operations = [
        migrations.AddField(
            model_name="filesystem",
            name="node",
            field=models.ForeignKey(
                to="maasserver.Node",
                blank=True,
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterField(
            model_name="filesystem",
            name="fstype",
            field=models.CharField(
                default="ext4",
                choices=[
                    ("ext2", "ext2"),
                    ("ext4", "ext4"),
                    ("xfs", "xfs"),
                    ("fat32", "fat32"),
                    ("vfat", "vfat"),
                    ("lvm-pv", "lvm"),
                    ("raid", "raid"),
                    ("raid-spare", "raid-spare"),
                    ("bcache-cache", "bcache-cache"),
                    ("bcache-backing", "bcache-backing"),
                    ("swap", "swap"),
                    ("ramfs", "ramfs"),
                    ("tmpfs", "tmpfs"),
                ],
                max_length=20,
            ),
        ),
    ]
