# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to ResourcePool changes."""

from django.db.models.signals import post_delete, post_save

from maasserver.models import ResourcePool
from maasserver.sqlalchemy import service_layer
from maasserver.utils.signals import SignalsManager
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder

signals = SignalsManager()


def post_created_resourcepool(sender, instance, created, **kwargs):
    if created:
        service_layer.services.openfga_tuples.create(
            OpenFGATupleBuilder.build_pool(str(instance.id))
        )


def post_delete_resourcepool(sender, instance, **kwargs):
    service_layer.services.openfga_tuples.delete_pool(instance.id)


signals.watch(post_save, post_created_resourcepool, sender=ResourcePool)
signals.watch(post_delete, post_delete_resourcepool, sender=ResourcePool)

# Enable all signals by default.
signals.enable()
