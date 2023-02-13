from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0068_drop_node_system_id_sequence")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="previous_status",
            field=models.IntegerField(
                choices=[
                    (0, "New"),
                    (1, "Commissioning"),
                    (2, "Failed commissioning"),
                    (3, "Missing"),
                    (4, "Ready"),
                    (5, "Reserved"),
                    (10, "Allocated"),
                    (9, "Deploying"),
                    (6, "Deployed"),
                    (7, "Retired"),
                    (8, "Broken"),
                    (11, "Failed deployment"),
                    (12, "Releasing"),
                    (13, "Releasing failed"),
                    (14, "Disk erasing"),
                    (15, "Failed disk erasing"),
                ],
                default=0,
                editable=False,
            ),
        )
    ]
