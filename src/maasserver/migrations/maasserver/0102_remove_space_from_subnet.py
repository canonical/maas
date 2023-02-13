from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0101_filesystem_btrfs_support")]

    operations = [
        migrations.AlterUniqueTogether(name="subnet", unique_together=set()),
        migrations.RemoveField(model_name="subnet", name="space"),
    ]
