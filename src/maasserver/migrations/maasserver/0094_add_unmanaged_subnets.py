from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0093_add_rdns_model")]

    operations = [
        migrations.AddField(
            model_name="subnet",
            name="managed",
            field=models.BooleanField(default=True),
        )
    ]
