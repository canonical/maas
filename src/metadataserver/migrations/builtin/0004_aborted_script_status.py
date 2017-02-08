# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)


class Migration(migrations.Migration):

    dependencies = [
        ('metadataserver', '0003_remove_noderesult'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scriptresult',
            name='status',
            field=models.IntegerField(choices=[(0, 'Script pending'), (1, 'Script running'), (2, 'Script passed'), (3, 'Script failed'), (4, 'Script timed out'), (5, 'Script aborted')], default=0),
        ),
    ]
