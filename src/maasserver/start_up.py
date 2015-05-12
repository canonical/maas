# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start-up utilities for the MAAS server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'start_up'
]

import logging

from django.db import connection
from django.db.utils import DatabaseError
from maasserver import (
    locks,
    security,
)
from maasserver.bootresources import (
    ensure_boot_source_definition,
    import_resources,
)
from maasserver.dns.config import dns_update_all_zones
from maasserver.fields import register_mac_type
from maasserver.models import (
    BootResource,
    BootSource,
    BootSourceSelection,
    NodeGroup,
)
from maasserver.triggers import register_all_triggers
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    get_psycopg2_exception,
    transactional,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.boot_images import list_boot_images
from provisioningserver.upgrade_cluster import create_gnupg_home
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    pause,
)
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


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
            yield deferToThread(inner_start_up)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except DatabaseError as e:
            psycopg2_exception = get_psycopg2_exception(e)
            if psycopg2_exception is None:
                maaslog.warn(
                    "Database error during start-up; "
                    "pausing for 3 seconds.")
            elif psycopg2_exception.pgcode is None:
                maaslog.warn(
                    "Database error during start-up (PostgreSQL error "
                    "not reported); pausing for 3 seconds.")
            else:
                maaslog.warn(
                    "Database error during start-up (PostgreSQL error %s); "
                    "pausing for 3 seconds.", psycopg2_exception.pgcode)
            logger.error("Database error during start-up", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        except:
            maaslog.warn("Error during start-up; pausing for 3 seconds.")
            logger.error("Error during start-up.", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        else:
            break


def start_import_on_upgrade():
    """Starts importing `BootResource`s on upgrade from MAAS where the boot
    images where only stored on the clusters."""
    # Do nothing, because `BootResource`s already exist.
    if BootResource.objects.exists():
        return

    # Do nothing if the cluster on the machine does not have
    # boot images present.
    boot_images = list_boot_images()
    if len(boot_images) == 0:
        return

    # Build the selections that need to be set based on the images
    # that live on the cluster.
    osystems = dict()
    for image in boot_images:
        osystem = image["osystem"]
        if osystem not in osystems:
            osystems[osystem] = {
                "arches": set(),
                "releases": set(),
                "labels": set(),
                }
        osystems[osystem]["arches"].add(
            image["architecture"])
        osystems[osystem]["releases"].add(
            image["release"])
        osystems[osystem]["labels"].add(
            image["label"])

    # We have no way to truly know which boot source this came
    # from, but since this should only occur on upgrade we
    # take the first source, which will be the default source and
    # apply the selection to that source.
    boot_source = BootSource.objects.first()

    # Clear all current selections and create the new selections
    # based on the information retrieved from list_boot_images.
    boot_source.bootsourceselection_set.all().delete()
    for osystem, options in osystems.items():
        for release in options["releases"]:
            BootSourceSelection.objects.create(
                boot_source=boot_source, os=osystem,
                release=release, arches=list(options["arches"]),
                subarches=["*"], labels=list(options["labels"]))

    # Start the import process for the user, since the cluster
    # already has images. Even though the cluster is usable the
    # region will not be usable until it has boot images as well.
    import_resources()


@transactional
@synchronised(locks.startup)
def inner_start_up():
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # Register our MAC data type with psycopg.
    register_mac_type(connection.cursor())

    # Make sure that the master nodegroup is created.
    # This must be serialized or we may initialize the master more than once.
    NodeGroup.objects.ensure_master()

    # Make sure that maas user's GNUPG home directory exists. This is needed
    # for importing of boot resources, which occurs on the region as well as
    # the clusters.
    create_gnupg_home()

    # If there are no boot-source definitions yet, create defaults.
    ensure_boot_source_definition()

    # Start import on upgrade if needed.
    start_import_on_upgrade()

    # Register all of the triggers.
    register_all_triggers()

    # Regenerate MAAS's DNS configuration.  This should be reentrant, really.
    dns_update_all_zones(reload_retry=True)
