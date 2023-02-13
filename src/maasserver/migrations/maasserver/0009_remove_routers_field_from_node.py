from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0008_use_new_arrayfield")]

    operations = [migrations.RemoveField(model_name="node", name="routers")]
