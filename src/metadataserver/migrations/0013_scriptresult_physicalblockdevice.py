from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0126_add_controllerinfo_model"),
        ("metadataserver", "0012_store_script_results"),
    ]

    operations = [
        migrations.AddField(
            model_name="scriptresult",
            name="physical_blockdevice",
            field=models.ForeignKey(
                to="maasserver.PhysicalBlockDevice",
                null=True,
                editable=False,
                blank=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterField(
            model_name="scriptresult",
            name="script",
            field=models.ForeignKey(
                to="metadataserver.Script",
                null=True,
                editable=False,
                blank=True,
                on_delete=models.CASCADE,
            ),
        ),
    ]
