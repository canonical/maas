from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0041_change_bmc_on_delete_to_set_null")]

    operations = [
        migrations.CreateModel(
            name="BMCRoutableRackControllerRelationship",
            fields=[
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("routable", models.BooleanField()),
                (
                    "bmc",
                    models.ForeignKey(
                        related_name="routable_rack_relationships",
                        to="maasserver.BMC",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "rack_controller",
                    models.ForeignKey(
                        related_name="routable_bmc_relationships",
                        to="maasserver.RackController",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(
                maasserver.models.cleansave.CleanSave,
                models.Model,
                object,
            ),
        ),
        migrations.AddField(
            model_name="bmc",
            name="routable_rack_controllers",
            field=models.ManyToManyField(
                related_name="routable_bmcs",
                through="maasserver.BMCRoutableRackControllerRelationship",
                to="maasserver.RackController",
                blank=True,
            ),
        ),
    ]
