from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0033_iprange_minor_changes")]

    operations = [
        migrations.RenameField(
            model_name="filesystem",
            old_name="mount_params",
            new_name="mount_options",
        )
    ]
