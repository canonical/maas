from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0047_fix_spelling_of_degraded")]

    operations = [
        migrations.AddField(
            model_name="subnet",
            name="allow_proxy",
            field=models.BooleanField(default=True),
        )
    ]
