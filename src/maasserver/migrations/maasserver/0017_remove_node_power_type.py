from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0016_migrate_power_data_node_to_bmc")]

    operations = [migrations.RemoveField(model_name="node", name="power_type")]
