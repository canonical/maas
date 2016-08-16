# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0075_modify_packagerepository'),
    ]

    operations = [
        migrations.AddField(
            model_name='interface',
            name='acquired',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
