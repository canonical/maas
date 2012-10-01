# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start up utilities for the MAAS server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'start_up'
    ]


from textwrap import dedent

from lockfile import FileLock
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
    )
from maasserver.dns import write_full_dns_config
from maasserver.enum import COMPONENT
from maasserver.maasavahi import setup_maas_avahi_service
from maasserver.models import (
    BootImage,
    NodeGroup,
    )

# Lock file used to prevent concurrent runs of the start_up() method.
LOCK_FILE_NAME = '/run/lock/' + __name__


# Timeout used to grab the filed-based lock used by the start_up() method.
LOCK_TIMEOUT = 60


def start_up():
    """Start up this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    This method is called when the MAAS application starts up.
    In production, it's called from the WSGI script so this shouldn't block
    at any costs.  It should simply call very simple methods or Celery tasks.

    The method will be executed multiple times if multiple processes are used
    but this method uses file-based locking to ensure that the methods it calls
    internally are not ran concurrently.
    """
    lock = FileLock(LOCK_FILE_NAME)
    lock.acquire(timeout=LOCK_TIMEOUT)
    try:
        inner_start_up()
    finally:
        lock.release()


def update_import_script_error():
    import_script = COMPONENT.IMPORT_PXE_FILES
    have_boot_images = BootImage.objects.all().exists()
    if not have_boot_images and get_persistent_error(import_script) is None:
        warning = dedent("""\
            The region controller does not know whether any boot images have
            been imported yet.  If this message does not disappear in 5
            minutes, there may be a communication problem between the region
            worker process and the region controller.  Check the region
            worker's logs for signs that it was unable to report to the MAAS
            API.
            """)
        register_persistent_error(import_script, warning)


def inner_start_up():
    # Publish the MAAS server existence over Avahi.
    setup_maas_avahi_service()

    # Make sure that the master nodegroup is created.
    NodeGroup.objects.ensure_master()

    # Regenerate MAAS's DNS configuration.
    write_full_dns_config(reload_retry=True)

    # Send secrets etc. to workers.
    NodeGroup.objects.refresh_workers()

    # Check whether we have boot images yet.
    update_import_script_error()
