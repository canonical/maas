from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0111_remove_component_error")]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="category",
            field=models.CharField(
                default="info",
                choices=[
                    ("error", "Error"),
                    ("warning", "Warning"),
                    ("success", "Success"),
                    ("info", "Informational"),
                ],
                max_length=10,
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="ident",
            field=models.CharField(
                null=True, default=None, max_length=40, blank=True
            ),
        ),
        migrations.AlterField(
            model_name="notification", name="message", field=models.TextField()
        ),
        migrations.AlterField(
            model_name="notification",
            name="user",
            field=models.ForeignKey(
                null=True,
                default=None,
                blank=True,
                to=settings.AUTH_USER_MODEL,
                on_delete=models.CASCADE,
            ),
        ),
    ]
