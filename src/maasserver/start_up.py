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


from maasserver.dns import write_full_dns_config
from maasserver.maasavahi import setup_maas_avahi_service
from maasserver.models import NodeGroup


def start_up():
    """Start up this MAAS server.

    This is used to:
    - make sure the singletons required by the application are created
    - sync the configuration of the external systems driven by MAAS

    This method is called when the MAAS application starts up.
    In production, it's called from the WSGI script so this shouldn't block
    at any costs.  It should simply call very simple methods or Celery tasks.
    """

    # Publish the MAAS server existence over Avahi.
    setup_maas_avahi_service()

    # Make sure that the master nodegroup is created.
    NodeGroup.objects.ensure_master()

    # Regenerate MAAS's DNS configuration.
    write_full_dns_config(reload_retry=True)
