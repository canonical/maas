from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0051_space_fabric_unique")]

    operations = [
        migrations.AddField(
            model_name="bootsourcecache",
            name="release_codename",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bootsourcecache",
            name="release_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bootsourcecache",
            name="support_eol",
            field=models.DateField(blank=True, null=True),
        ),
    ]
