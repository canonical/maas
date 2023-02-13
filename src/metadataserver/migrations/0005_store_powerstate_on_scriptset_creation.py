from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0004_aborted_script_status")]

    operations = [
        migrations.AddField(
            model_name="scriptset",
            name="power_state_before_transition",
            field=models.CharField(
                default="unknown",
                max_length=10,
                editable=False,
                choices=[
                    ("on", "On"),
                    ("off", "Off"),
                    ("unknown", "Unknown"),
                    ("error", "Error"),
                ],
            ),
        )
    ]
