from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0080_change_packagerepository_url_type")]

    operations = [
        migrations.AlterField(
            model_name="bootsourcecache",
            name="arch",
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name="bootsourcecache",
            name="label",
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name="bootsourcecache",
            name="os",
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name="bootsourcecache",
            name="release",
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name="bootsourcecache",
            name="subarch",
            field=models.CharField(max_length=32),
        ),
    ]
