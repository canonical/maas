from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0108_generate_bmc_names")]

    operations = [
        migrations.AlterField(
            model_name="bmc",
            name="name",
            field=models.CharField(
                blank=True, default="", unique=True, max_length=255
            ),
        )
    ]
