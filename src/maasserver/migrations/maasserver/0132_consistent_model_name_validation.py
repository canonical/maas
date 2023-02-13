import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0131_update_event_model_for_audit_logs")]

    operations = [
        migrations.AlterField(
            model_name="fabric",
            name="class_type",
            field=models.CharField(
                validators=[
                    django.core.validators.RegexValidator("^\\w[ \\w-]*$")
                ],
                null=True,
                blank=True,
                max_length=256,
            ),
        ),
        migrations.AlterField(
            model_name="fannetwork",
            name="name",
            field=models.CharField(
                validators=[
                    django.core.validators.RegexValidator("^\\w[ \\w-]*$")
                ],
                help_text="Name of the fan network",
                unique=True,
                max_length=256,
            ),
        ),
        migrations.AlterField(
            model_name="vlan",
            name="name",
            field=models.CharField(
                validators=[
                    django.core.validators.RegexValidator("^\\w[ \\w-]*$")
                ],
                null=True,
                blank=True,
                max_length=256,
            ),
        ),
        migrations.AlterField(
            model_name="zone",
            name="name",
            field=models.CharField(
                validators=[
                    django.core.validators.RegexValidator("^\\w[ \\w-]*$")
                ],
                unique=True,
                max_length=256,
            ),
        ),
    ]
