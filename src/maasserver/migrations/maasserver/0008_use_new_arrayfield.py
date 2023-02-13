import django.contrib.postgres.fields
from django.db import migrations, models

import maasserver.fields


class Migration(migrations.Migration):
    dependencies = [("maasserver", "0007_create_node_proxy_models")]

    operations = [
        migrations.AlterField(
            model_name="blockdevice",
            name="tags",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="bootsourceselection",
            name="arches",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="bootsourceselection",
            name="labels",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="bootsourceselection",
            name="subarches",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="interface",
            name="tags",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="node",
            name="routers",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=maasserver.fields.MACAddressField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
        migrations.AlterField(
            model_name="subnet",
            name="dns_servers",
            field=django.contrib.postgres.fields.ArrayField(
                size=None,
                base_field=models.TextField(),
                null=True,
                blank=True,
                default=list,
            ),
        ),
    ]
