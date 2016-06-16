# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start-up utilities for the MAAS server."""

__all__ = [
    'start_up'
]

import logging
from socket import gethostname

from django.db import connection
from django.db.models import Q
from django.db.utils import DatabaseError
from maasserver import (
    is_master_process,
    locks,
    security,
)
from maasserver.enum import NODE_TYPE
from maasserver.fields import register_mac_type
from maasserver.models.domain import dns_kms_setting_changed
from maasserver.models.node import (
    Node,
    RegionController,
    typecast_node,
)
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    get_one,
    get_psycopg2_exception,
    post_commit_do,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.worker_user import get_worker_user
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.env import (
    get_maas_id,
    set_maas_id,
)
from provisioningserver.utils.ipaddr import get_mac_addresses
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    pause,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.python import log


maaslog = get_maas_logger("start-up")
logger = logging.getLogger(__name__)


@asynchronous(timeout=FOREVER)
@inlineCallbacks
def start_up():
    """Perform start-up tasks for this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    The method will be executed multiple times if multiple processes are used
    but this method uses database locking to ensure that the methods it calls
    internally are not run concurrently.
    """
    while True:
        try:
            # Get the shared secret from Tidmouth sheds which was generated
            # when Sir Topham Hatt graduated Sodor Academy. (Ensure we have a
            # shared-secret so that a cluster on the same host as this region
            # can authenticate.)
            yield security.get_shared_secret()
            # Execute other start-up tasks that must not run concurrently with
            # other invocations of themselves, across the whole of this MAAS
            # installation.
            yield deferToDatabase(inner_start_up)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except DatabaseError as e:
            psycopg2_exception = get_psycopg2_exception(e)
            if psycopg2_exception is None:
                maaslog.warning(
                    "Database error during start-up; "
                    "pausing for 3 seconds.")
            elif psycopg2_exception.pgcode is None:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error "
                    "not reported); pausing for 3 seconds.")
            else:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error %s); "
                    "pausing for 3 seconds.", psycopg2_exception.pgcode)
            logger.error("Database error during start-up", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        except:
            maaslog.warning("Error during start-up; pausing for 3 seconds.")
            logger.error("Error during start-up.", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        else:
            break


@with_connection  # Needed by the following lock.
@synchronised(locks.startup)
@transactional
def inner_start_up():
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # Register our MAC data type with psycopg.
    register_mac_type(connection.cursor())

    def refresh_region(region_obj):
        # The RegionAdvertisingService uses
        # RegionController.objects.get_running_controller() which calls
        # get_maas_id() to find the system_id of the running region. If this
        # isn't done here RegionAdvertisingService won't be able to figure out
        # the region object for the running machine.
        set_maas_id(region_obj.system_id)
        d = region_obj.refresh()
        d.addErrback(log.err, "Failure when refreshing region")
        return d

    # Only perform the following if the master process for the
    # region controller.
    if is_master_process():
        # Freshen the kms SRV records.
        dns_kms_setting_changed()

        region_obj = create_region_obj()
        post_commit_do(reactor.callLater, 0, refresh_region, region_obj)
        # Trigger post commit
        region_obj.save()


def create_region_obj():
    region_id = get_maas_id()
    hostname = gethostname()
    update_fields = []
    region_filter = Q() if region_id is None else Q(system_id=region_id)
    region_filter |= Q(hostname=hostname)
    region_filter |= Q(interface__mac_address__in=get_mac_addresses())
    region_obj = get_one(Node.objects.filter(region_filter).distinct())
    if region_obj is None:
        # This is the first time MAAS has run on this node.
        region_obj = RegionController.objects.create(hostname=hostname)
    else:
        # Already exists. Make sure it's configured as a region.
        if region_obj.node_type == NODE_TYPE.RACK_CONTROLLER:
            region_obj.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
            update_fields.append("node_type")
        elif not region_obj.is_region_controller:
            region_obj.node_type = NODE_TYPE.REGION_CONTROLLER
            update_fields.append("node_type")
        region_obj = typecast_node(region_obj, RegionController)

    if region_obj.owner is None:
        region_obj.owner = get_worker_user()
        update_fields.append("owner")

    if len(update_fields) > 0:
        region_obj.save(update_fields=update_fields)

    return region_obj
