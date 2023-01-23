from django.db import migrations, models

import maasserver.migrations.fields


class Migration(migrations.Migration):

    dependencies = [
        ("metadataserver", "0010_scriptresult_time_and_script_title")
    ]

    operations = [
        migrations.AddField(
            model_name="script",
            name="hardware_type",
            field=models.IntegerField(
                default=0,
                choices=[
                    (0, "Node"),
                    (1, "CPU"),
                    (2, "Memory"),
                    (3, "Storage"),
                ],
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="packages",
            field=maasserver.migrations.fields.JSONObjectField(
                blank=True, default={}
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="parallel",
            field=models.IntegerField(
                default=0,
                choices=[
                    (0, "Disabled"),
                    (1, "Run along other instances of this script"),
                    (2, "Run along any other script."),
                ],
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="parameters",
            field=maasserver.migrations.fields.JSONObjectField(
                blank=True, default={}
            ),
        ),
        migrations.AddField(
            model_name="script",
            name="results",
            field=maasserver.migrations.fields.JSONObjectField(
                blank=True, default={}
            ),
        ),
        migrations.AddField(
            model_name="scriptresult",
            name="parameters",
            field=maasserver.migrations.fields.JSONObjectField(
                blank=True, default={}
            ),
        ),
    ]
