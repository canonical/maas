# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0128_events_created_index")]

    operations = [
        migrations.AddField(
            model_name="node",
            name="install_rackd",
            field=models.BooleanField(default=False),
        )
    ]
