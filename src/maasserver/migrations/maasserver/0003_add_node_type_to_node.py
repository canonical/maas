from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0002_remove_candidate_name_model")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="node_type",
            field=models.IntegerField(
                default=0,
                editable=False,
                choices=[
                    (0, "Machine"),
                    (1, "Device"),
                    (2, "Rack controller"),
                ],
            ),
        )
    ]
