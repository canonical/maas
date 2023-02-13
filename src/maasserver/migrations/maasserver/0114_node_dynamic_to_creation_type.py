from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0113_set_filepath_limit_to_linux_max")]

    operations = [
        migrations.RemoveField(model_name="node", name="dynamic"),
        migrations.AddField(
            model_name="node",
            name="creation_type",
            field=models.IntegerField(default=1),
        ),
    ]
