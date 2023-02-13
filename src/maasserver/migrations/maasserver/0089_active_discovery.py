from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0088_remove_node_disable_ipv4")]

    operations = [
        migrations.RemoveField(
            model_name="interface", name="active_discovery_params"
        ),
        migrations.RemoveField(
            model_name="interface", name="active_discovery_state"
        ),
        migrations.AddField(
            model_name="subnet",
            name="active_discovery",
            field=models.BooleanField(default=False),
        ),
    ]
