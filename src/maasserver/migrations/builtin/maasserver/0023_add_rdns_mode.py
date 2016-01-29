# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0022_create_zone_serial_sequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnet',
            name='rdns_mode',
            field=models.IntegerField(choices=[(0, 'Disabled'), (1, 'Enabled'), (2, 'Enabled, with rfc2317 glue zone.')], default=2),
        ),
    ]
