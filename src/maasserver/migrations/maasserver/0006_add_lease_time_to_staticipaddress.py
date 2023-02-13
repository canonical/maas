from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0005_delete_installable_from_node")]

    operations = [
        migrations.AddField(
            model_name="staticipaddress",
            name="lease_time",
            field=models.IntegerField(default=0, editable=False),
        )
    ]
