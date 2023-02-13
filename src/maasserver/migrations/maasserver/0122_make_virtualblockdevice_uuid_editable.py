from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0121_relax_staticipaddress_unique_constraint")
    ]

    operations = [
        migrations.AlterField(
            model_name="virtualblockdevice",
            name="uuid",
            field=models.CharField(unique=True, max_length=36),
        )
    ]
