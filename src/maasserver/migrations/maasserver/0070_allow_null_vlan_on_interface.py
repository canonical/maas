from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0069_add_previous_node_status_to_node")]

    operations = [
        migrations.AlterField(
            model_name="interface",
            name="vlan",
            field=models.ForeignKey(
                null=True,
                blank=True,
                to="maasserver.VLAN",
                on_delete=django.db.models.deletion.PROTECT,
            ),
        )
    ]
