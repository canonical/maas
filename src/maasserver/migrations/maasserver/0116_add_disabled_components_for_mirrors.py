import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0115_additional_boot_resource_filetypes")]

    operations = [
        migrations.AddField(
            model_name="packagerepository",
            name="disabled_components",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(),
                size=None,
                default=list,
                blank=True,
                null=True,
            ),
        )
    ]
