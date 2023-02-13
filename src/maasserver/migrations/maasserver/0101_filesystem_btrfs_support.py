from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0100_migrate_spaces_from_subnet_to_vlan")]

    operations = [
        migrations.AlterField(
            model_name="filesystem",
            name="fstype",
            field=models.CharField(
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
                    ("btrfs", "btrfs"),
                ],
                max_length=20,
                default="ext4",
            ),
        )
    ]
