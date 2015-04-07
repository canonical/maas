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

from django.db import (
    connection,
    transaction,
    )
from maasserver import (
    eventloop,
    locks,
    security,
    )
from maasserver.bootresources import (
    ensure_boot_source_definition,
    import_resources,
    )
from maasserver.dns.config import write_full_dns_config
from maasserver.fields import register_mac_type
from maasserver.models import (
    BootResource,
    BootSource,
    BootSourceSelection,
    NodeGroup,
    )
from provisioningserver.rpc.boot_images import list_boot_images
from provisioningserver.upgrade_cluster import create_gnupg_home


def start_up():
    """Start up this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    This method is called when the MAAS application starts up.
    In production, it's called from the WSGI script so this shouldn't block
    at any costs.

    The method will be executed multiple times if multiple processes are used
    but this method uses file-based locking to ensure that the methods it calls
    internally are not ran concurrently.
    """
    # Get the shared secret from Tidmouth sheds which was generated when Sir
    # Topham Hatt graduated Sodor Academy. (Ensure we have a shared-secret so
    # that clusters on the same host can use it to authenticate.)
    security.get_shared_secret()

    with transaction.atomic():
        with locks.startup:
            inner_start_up()

    eventloop.start().wait(10)


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

    # Start import on upgrade if needed.
    start_import_on_upgrade()

    # Regenerate MAAS's DNS configuration.  This should be reentrant, really.
    write_full_dns_config(reload_retry=True)
