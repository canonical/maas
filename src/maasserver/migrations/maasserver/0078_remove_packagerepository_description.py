# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0077_static_routes")]

    operations = [
        migrations.RemoveField(
            model_name="packagerepository", name="description"
        )
    ]
