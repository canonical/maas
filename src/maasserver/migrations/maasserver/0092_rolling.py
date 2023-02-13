from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0091_v2_to_v3")]

    operations = [
        migrations.AddField(
            model_name="bootresource",
            name="rolling",
            field=models.BooleanField(default=False),
        )
    ]
