# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Start up utilities for the MAAS server."""

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

from textwrap import dedent

from django.db import (
    connection,
    transaction,
    )
from maasserver import (
    eventloop,
    locks,
    )
from maasserver.bootresources import ensure_boot_source_definition
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
    )
from maasserver.dns.config import write_full_dns_config
from maasserver.enum import COMPONENT
from maasserver.fields import register_mac_type
from maasserver.models import (
    BootImage,
    NodeGroup,
    )
from provisioningserver.upgrade_cluster import create_gnupg_home


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
    with transaction.atomic():
        with locks.startup:
            inner_start_up()

    eventloop.start().wait(10)

    post_start_up()


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
    """Startup jobs that must run serialized w.r.t. other starting servers."""
    # Register our MAC data type with psycopg.
    register_mac_type(connection.cursor())

    # Make sure that the master nodegroup is created.
    # This must be serialized or we may initialize the master more than once.
    NodeGroup.objects.ensure_master()

    # Make sure that maas user's GNUPG home directory exists. This is needed
    # for importing of boot resources, that now occurs on the region as well
    # as the clusters.
    create_gnupg_home()

    # If no boot-source definitions yet, create the default definition.
    ensure_boot_source_definition()

    # Regenerate MAAS's DNS configuration.  This should be reentrant, really.
    write_full_dns_config(reload_retry=True)

    # Check whether we have boot images yet.
    update_import_script_error()


def post_start_up():
    """Startup jobs that can run after the critical section."""
    # Send secrets etc. to workers.
    NodeGroup.objects.refresh_workers()
