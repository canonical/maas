from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0126_add_controllerinfo_model")]

    operations = [
        migrations.CreateModel(
            name="NodeMetadata",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        auto_created=True,
                        verbose_name="ID",
                        serialize=False,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("key", models.CharField(max_length=64)),
                ("value", models.TextField()),
                (
                    "node",
                    models.ForeignKey(
                        to="maasserver.Node",
                        editable=False,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={
                "verbose_name": "NodeMetadata",
                "verbose_name_plural": "NodeMetadata",
            },
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="nodemetadata", unique_together={("node", "key")}
        ),
    ]
