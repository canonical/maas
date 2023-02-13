from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("metadataserver", "0002_script_models"),
        ("maasserver", "0104_notifications_dismissals"),
    ]

    operations = [
        migrations.AddField(
            model_name="node",
            name="current_commissioning_script_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="metadataserver.ScriptSet",
                related_name="+",
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="current_installation_script_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="metadataserver.ScriptSet",
                related_name="+",
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="current_testing_script_set",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="metadataserver.ScriptSet",
                related_name="+",
            ),
        ),
    ]
