# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to services."""

__all__ = [
    "update_services",
]

from maasserver.models.node import RackController
from maasserver.models.service import Service
from maasserver.utils.orm import transactional
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def update_services(system_id, services):
    """Update services on rack controller with `system_id`.

    :param services: List of services as found in
        :py:class`~provisioningserver.rpc.region.UpdateServices`.

    :raises NoSuchCluster: If the rack controller identified by `system_id`
        does not exist.
    """
    try:
        rack = RackController.objects.get(system_id=system_id)
    except RackController.DoesNotExist:
        raise NoSuchCluster.from_uuid(system_id)

    # Update each service.
    for service in services:
        Service.objects.update_service_for(
            rack, service['name'], service['status'], service['status_info'])
    return {}
