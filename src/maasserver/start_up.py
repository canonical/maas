# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start-up utilities for the MAAS server."""


import logging

from django.db import connection
from django.db.utils import DatabaseError
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver import locks, security
from maasserver.deprecations import sync_deprecation_notifications
from maasserver.fields import register_mac_type
from maasserver.models.config import Config
from maasserver.models.domain import dns_kms_setting_changed
from maasserver.models.node import RegionController
from maasserver.models.notification import Notification
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    get_psycopg2_exception,
    post_commit_do,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from metadataserver.builtin_scripts import load_builtin_scripts
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.maas_certificates import generate_certificate_if_needed
from provisioningserver.utils.twisted import asynchronous, FOREVER, pause

maaslog = get_maas_logger("start-up")
logger = logging.getLogger(__name__)
log = LegacyLogger()


@asynchronous(timeout=FOREVER)
@inlineCallbacks
def start_up(master=False):
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
            yield deferToDatabase(inner_start_up, master=master)
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except DatabaseError as e:
            psycopg2_exception = get_psycopg2_exception(e)
            if psycopg2_exception is None:
                maaslog.warning(
                    "Database error during start-up; " "pausing for 3 seconds."
                )
            elif psycopg2_exception.pgcode is None:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error "
                    "not reported); pausing for 3 seconds."
                )
            else:
                maaslog.warning(
                    "Database error during start-up (PostgreSQL error %s); "
                    "pausing for 3 seconds.",
                    psycopg2_exception.pgcode,
                )
            logger.error("Database error during start-up", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        except Exception:
            maaslog.warning("Error during start-up; pausing for 3 seconds.")
            logger.error("Error during start-up.", exc_info=True)
            yield pause(3.0)  # Wait 3 seconds before having another go.
        else:
            break


@with_connection  # Needed by the following lock.
@synchronised(locks.startup)
@transactional
def inner_start_up(master=False):
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # Register our MAC data type with psycopg.
    register_mac_type(connection.cursor())

    # All commissioning and testing scripts are stored in the database. For
    # a commissioning ScriptSet to be created Scripts must exist first. Call
    # this early, only on the master process, to ensure they exist and are
    # only created once. If get_or_create_running_controller() is called before
    # this it will fail on first run.
    if master:
        load_builtin_scripts()

    # Ensure the this region is represented in the database. The first regiond
    # to pass through inner_start_up on this host can do this; it should NOT
    # be restricted to masters only. This also ensures that the MAAS ID is set
    # on the filesystem; it will be done in a post-commit hook and will thus
    # happen before `locks.startup` is released.
    region = RegionController.objects.get_or_create_running_controller()
    # Ensure that uuid is created after creating
    RegionController.objects.get_or_create_uuid()

    # Only perform the following if the master process for the
    # region controller.
    if master:
        # Freshen the kms SRV records.
        dns_kms_setting_changed()

        # Make sure the commissioning distro series is still a supported LTS.
        commissioning_distro_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        ubuntu = UbuntuOS()
        if commissioning_distro_series not in (
            ubuntu.get_supported_commissioning_releases()
        ):
            Config.objects.set_config(
                "commissioning_distro_series",
                ubuntu.get_default_commissioning_release(),
            )
            Notification.objects.create_info_for_admins(
                "Ubuntu %s is no longer a supported commissioning "
                "series. Ubuntu %s has been automatically selected."
                % (
                    commissioning_distro_series,
                    ubuntu.get_default_commissioning_release(),
                ),
                ident="commissioning_release_deprecated",
            )

        # Update deprecation notifications if needed
        sync_deprecation_notifications()

        # Refresh soon after this transaction is in.
        post_commit_do(reactor.callLater, 0, refreshRegion, region)

        # Create a certificate for the region.
        post_commit_do(reactor.callLater, 0, generate_certificate_if_needed)


def refreshRegion(region):
    """Refresh the region controller, logging errors."""
    return region.refresh().addErrback(
        log.err, "Failure when refreshing region."
    )
