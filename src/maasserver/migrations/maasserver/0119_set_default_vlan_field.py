# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import maasserver.models.subnet


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0118_add_iscsi_storage_pod")]

    operations = [
        migrations.AlterField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                to="maasserver.VLAN",
                on_delete=django.db.models.deletion.PROTECT,
                default=maasserver.models.subnet.get_default_vlan,
            ),
        )
    ]
