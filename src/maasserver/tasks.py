# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Maasserver tasks that are run in Celery workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'import_boot_images_on_schedule',
    ]


from celery.task import task
from maasserver.models import NodeGroup


@task
def import_boot_images_on_schedule(**kwargs):
    """Periodic import of boot images, triggered from Celery schedule."""
    NodeGroup.objects.import_boot_images_accepted_clusters()
