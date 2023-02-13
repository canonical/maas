from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maasserver", "0028_update_default_vlan_on_interface_and_subnet")
    ]

    operations = [
        migrations.AddField(
            model_name="subnet",
            name="rdns_mode",
            field=models.IntegerField(
                choices=[
                    (0, "Disabled"),
                    (1, "Enabled"),
                    (2, "Enabled, with rfc2317 glue zone."),
                ],
                default=2,
            ),
        )
    ]
