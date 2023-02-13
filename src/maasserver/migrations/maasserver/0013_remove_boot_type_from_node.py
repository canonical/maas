from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0012_drop_dns_fields")]

    operations = [migrations.RemoveField(model_name="node", name="boot_type")]
