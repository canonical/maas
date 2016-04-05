# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)
import django.db.models.deletion
import maasserver.models.interface
import maasserver.models.subnet


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0048_add_subnet_allow_proxy'),
    ]

    operations = [
        migrations.AddField(
            model_name='vlan',
            name='external_dhcp_present',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AlterField(
            model_name='interface',
            name='vlan',
            field=models.ForeignKey(to='maasserver.VLAN', on_delete=django.db.models.deletion.PROTECT, default=maasserver.models.interface.get_default_vlan),
        ),
        migrations.AlterField(
            model_name='subnet',
            name='vlan',
            field=models.ForeignKey(to='maasserver.VLAN', on_delete=django.db.models.deletion.PROTECT, default=maasserver.models.subnet.get_default_vlan),
        ),
    ]
