# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.core.validators
from django.db import (
    migrations,
    models,
)
import maasserver.fields
import maasserver.models.cleansave


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0013_remove_boot_type_from_node'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegionControllerProcess',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(editable=False)),
                ('updated', models.DateTimeField(editable=False)),
                ('pid', models.IntegerField()),
            ],
            options={
                'ordering': ['pid'],
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name='RegionControllerProcessEndpoint',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(editable=False)),
                ('updated', models.DateTimeField(editable=False)),
                ('address', maasserver.fields.MAASIPAddressField(editable=False)),
                ('port', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(65535)], default=0)),
                ('process', models.ForeignKey(related_name='endpoints', to='maasserver.RegionControllerProcess')),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name='RegionController',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('maasserver.node',),
        ),
        migrations.AlterField(
            model_name='node',
            name='node_type',
            field=models.IntegerField(editable=False, choices=[(0, 'Machine'), (1, 'Device'), (2, 'Rack controller'), (3, 'Region controller')], default=0),
        ),
        migrations.AlterField(
            model_name='node',
            name='nodegroup',
            field=models.ForeignKey(to='maasserver.NodeGroup', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='regioncontrollerprocess',
            name='region',
            field=models.ForeignKey(related_name='processes', to='maasserver.RegionController'),
        ),
        migrations.AddField(
            model_name='node',
            name='dns_process',
            field=models.OneToOneField(to='maasserver.RegionControllerProcess', null=True, related_name='+', editable=False),
        ),
        migrations.AlterUniqueTogether(
            name='regioncontrollerprocessendpoint',
            unique_together=set([('process', 'address', 'port')]),
        ),
        migrations.AlterUniqueTogether(
            name='regioncontrollerprocess',
            unique_together=set([('region', 'pid')]),
        ),
    ]
