from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0087_add_completed_intro_to_userprofile")]

    operations = [
        migrations.RemoveField(model_name="node", name="disable_ipv4")
    ]
