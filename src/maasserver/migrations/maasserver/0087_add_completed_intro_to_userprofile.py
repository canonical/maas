from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0086_remove_powerpc_from_ports_arches")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="completed_intro",
            field=models.BooleanField(default=False),
        )
    ]
