from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0261_interface_nodeconfig_only"),
    ]

    operations = [
        # table changes moved from 0256_blockdevice_nodeconfig_only
        migrations.AlterField(
            model_name="blockdevice",
            name="node_config",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="maasserver.NodeConfig",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="blockdevice",
            unique_together={("node_config", "name")},
        ),
        migrations.RemoveField(
            model_name="blockdevice",
            name="node",
        ),
        # table changes moved from 0261_interface_nodeconfig_only
        migrations.AlterUniqueTogether(
            name="interface",
            unique_together={("node_config", "name")},
        ),
        migrations.RemoveField(
            model_name="interface",
            name="node",
        ),
    ]
