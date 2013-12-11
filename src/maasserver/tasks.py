# Copyright 2013 Canonical Ltd.  This software is licensed under the
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
    'cleanup_old_nonces',
    'import_boot_images_on_schedule',
    ]


from celery.task import task
from maasserver import (
    logger,
    nonces_cleanup,
    )
from maasserver.models import NodeGroup


@task
def cleanup_old_nonces(**kwargs):
    nb_nonces_deleted = nonces_cleanup.cleanup_old_nonces()
    logger.info("%d expired nonce(s) cleaned up." % nb_nonces_deleted)


@task
def import_boot_images_on_schedule(**kwargs):
    """Periodic import of boot images, triggered from Celery schedule."""
    NodeGroup.objects.import_boot_images_accepted_clusters()
