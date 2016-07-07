# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import (
    migrations,
    models,
)


class Migration(migrations.Migration):

    dependencies = [
        ('maasserver', '0067_add_previous_node_status_to_node'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bootresourcefile',
            name='filetype',
            field=models.CharField(editable=False, default='root-tgz', max_length=20, choices=[('root-tgz', 'Root Image (tar.gz)'), ('root-dd', 'Root Compressed DD (dd -> tar.gz)'), ('root-image.gz', 'Compressed Root Image'), ('squashfs', 'SquashFS Root Image'), ('boot-kernel', 'Linux ISCSI Kernel'), ('boot-initrd', 'Initial ISCSI Ramdisk'), ('boot-dtb', 'ISCSI Device Tree Blob')]),
        ),
    ]
