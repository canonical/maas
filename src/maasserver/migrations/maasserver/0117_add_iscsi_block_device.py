from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0116_add_disabled_components_for_mirrors")]

    operations = [
        migrations.CreateModel(
            name="ISCSIBlockDevice",
            fields=[
                (
                    "blockdevice_ptr",
                    models.OneToOneField(
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        to="maasserver.BlockDevice",
                        serialize=False,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "target",
                    models.CharField(
                        max_length=4096,
                        unique=True,
                    ),
                ),
            ],
            bases=("maasserver.blockdevice",),
        )
    ]
