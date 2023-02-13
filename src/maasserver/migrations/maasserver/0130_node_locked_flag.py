from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0129_add_install_rackd_flag")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="locked",
            field=models.BooleanField(default=False),
        )
    ]
