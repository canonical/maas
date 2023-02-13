from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0036_add_service_model")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="last_image_sync",
            field=models.DateTimeField(
                default=None, null=True, editable=False
            ),
        )
    ]
