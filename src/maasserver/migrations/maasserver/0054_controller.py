from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0053_add_ownerdata_model")]

    operations = [
        migrations.CreateModel(
            name="Controller",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        )
    ]
