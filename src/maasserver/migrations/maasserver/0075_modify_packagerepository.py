import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0074_merge")]

    operations = [
        migrations.RemoveField(model_name="packagerepository", name="distro"),
        migrations.RemoveField(model_name="packagerepository", name="pockets"),
        migrations.AddField(
            model_name="packagerepository",
            name="disabled_pockets",
            field=django.contrib.postgres.fields.ArrayField(
                blank=True,
                null=True,
                default=list,
                base_field=models.TextField(),
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="packagerepository",
            name="distributions",
            field=django.contrib.postgres.fields.ArrayField(
                blank=True,
                null=True,
                default=list,
                base_field=models.TextField(),
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="packagerepository",
            name="key",
            field=models.TextField(blank=True, default=""),
        ),
    ]
