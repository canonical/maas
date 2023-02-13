from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0110_notification_category")]

    operations = [migrations.DeleteModel(name="ComponentError")]
