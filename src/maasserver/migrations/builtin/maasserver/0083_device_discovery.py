# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)
import maasserver.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0082_add_kflavor'),
    ]

    operations = [
        migrations.CreateModel(
            name='Discovery',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('discovery_id', models.CharField(unique=True, max_length=256, null=True, editable=False)),
                ('ip', maasserver.fields.MAASIPAddressField(blank=True, null=True, editable=False, verbose_name='IP', default=None)),
                ('mac_address', maasserver.fields.MACAddressField(blank=True, null=True, editable=False)),
                ('last_seen', models.DateTimeField(editable=False)),
                ('hostname', maasserver.fields.DomainNameField(editable=False, max_length=256, null=True)),
                ('observer_system_id', models.CharField(max_length=41, editable=False)),
                ('observer_hostname', maasserver.fields.DomainNameField(editable=False, max_length=256, null=True)),
                ('observer_interface_name', models.CharField(max_length=255, editable=False)),
                ('fabric_name', models.CharField(max_length=256, blank=True, null=True, editable=False)),
                ('vid', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'managed': False,
                'verbose_name': 'Discovery',
                'verbose_name_plural': 'Discoveries',
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
    ]
