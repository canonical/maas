from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0112_update_notification")]

    operations = [
        migrations.AlterField(
            model_name="blockdevice",
            name="id_path",
            field=models.FilePathField(
                help_text="Path of by-id alias. (e.g. /dev/disk/by-id/wwn-0x50004...)",
                max_length=4096,
                null=True,
                blank=True,
            ),
        ),
        migrations.AlterField(
            model_name="bootsource",
            name="keyring_filename",
            field=models.FilePathField(
                help_text="The path to the keyring file for this BootSource.",
                max_length=4096,
                blank=True,
            ),
        ),
    ]
