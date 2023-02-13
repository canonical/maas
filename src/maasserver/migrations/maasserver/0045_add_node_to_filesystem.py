from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0044_remove_di_bootresourcefiles")]

    operations = [
        migrations.AlterField(
            model_name="filesystem",
            name="node",
            field=models.ForeignKey(
                related_name="special_filesystems",
                null=True,
                to="maasserver.Node",
                blank=True,
                on_delete=models.CASCADE,
            ),
        )
    ]
