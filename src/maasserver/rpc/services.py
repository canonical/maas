# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to services."""

from logging import getLogger

from maasserver.models.node import RackController
from maasserver.models.service import Service
from maasserver.utils.orm import transactional
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.utils.twisted import synchronous

log = getLogger(__name__)


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
        raise NoSuchCluster.from_uuid(system_id)  # noqa: B904

    # Update each service. For now, when a service is not recognised, log it
    # and move on, but what we really need is as UpdateServicesV2 RPC call in
    # order to report this error back to the rack properly.
    for service in services:
        try:
            Service.objects.update_service_for(
                rack,
                service["name"],
                service["status"],
                service["status_info"],
            )
        except Service.DoesNotExist:
            log.error(
                "Rack %s reported status for %r but this is not a recognised "
                "service (status=%r, info=%r).",
                rack.system_id,
                service["name"],
                service["status"],
                service["status_info"],
            )

    return {}
