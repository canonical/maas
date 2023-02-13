from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0117_add_iscsi_block_device")]

    operations = [
        migrations.AddField(
            model_name="bmc",
            name="iscsi_storage",
            field=models.BigIntegerField(default=-1),
        ),
        migrations.AddField(
            model_name="podhints",
            name="cpu_speed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="podhints",
            name="iscsi_storage",
            field=models.BigIntegerField(default=-1),
        ),
    ]
