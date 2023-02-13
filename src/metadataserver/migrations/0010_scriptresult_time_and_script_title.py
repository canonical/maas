from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadataserver", "0009_remove_noderesult_schema")]

    operations = [
        migrations.AddField(
            model_name="script",
            name="title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="scriptresult",
            name="ended",
            field=models.DateTimeField(editable=False, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="scriptresult",
            name="started",
            field=models.DateTimeField(editable=False, null=True, blank=True),
        ),
    ]
