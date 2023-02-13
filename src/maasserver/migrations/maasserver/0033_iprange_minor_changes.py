from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0032_loosen_vlan")]

    operations = [
        migrations.AlterField(
            model_name="iprange",
            name="end_ip",
            field=models.GenericIPAddressField(verbose_name="End IP"),
        ),
        migrations.AlterField(
            model_name="iprange",
            name="start_ip",
            field=models.GenericIPAddressField(verbose_name="Start IP"),
        ),
        migrations.AlterField(
            model_name="iprange",
            name="type",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("dynamic", "Dynamic IP Range"),
                    ("reserved", "Reserved IP Range"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="iprange",
            name="user",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                null=True,
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                blank=True,
            ),
        ),
    ]
