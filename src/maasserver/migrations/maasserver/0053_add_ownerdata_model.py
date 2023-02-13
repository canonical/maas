from django.db import migrations, models

import maasserver.models.cleansave


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0052_add_codename_title_eol_to_bootresourcecache")
    ]

    operations = [
        migrations.CreateModel(
            name="OwnerData",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("key", models.CharField(max_length=255)),
                ("value", models.TextField()),
                (
                    "node",
                    models.ForeignKey(
                        to="maasserver.Node", on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name="ownerdata", unique_together={("node", "key")}
        ),
    ]
