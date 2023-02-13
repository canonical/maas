from django.db import migrations, models

import maasserver.models.cleansave


def grab_data(apps, schema_editor):
    NodeGroupInterface = apps.get_model("maasserver", "NodeGroupInterface")
    NodeGroupToRackController = apps.get_model(
        "maasserver", "NodeGroupToRackController"
    )

    for ngi in NodeGroupInterface.objects.all():
        # Don't store interfaces which are unmanaged(0).
        if ngi.management != 0:
            NodeGroupToRackController.objects.create(
                uuid=ngi.nodegroup.uuid, subnet=ngi.subnet
            )


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0019_add_iprange")]

    operations = [
        migrations.CreateModel(
            name="NodeGroupToRackController",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        primary_key=True,
                        serialize=False,
                        auto_created=True,
                    ),
                ),
                ("uuid", models.CharField(max_length=36)),
                (
                    "subnet",
                    models.ForeignKey(
                        to="maasserver.Subnet", on_delete=models.CASCADE
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
        migrations.RunPython(grab_data),
    ]
