# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Glue to publish MAAS over Avahi."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.models import Config
from maasserver.zeroconfservice import ZeroconfService


class MAASAvahiService:
    """Publishes the MAAS server existence over Avahi.

    The server is exported as '%s MAAS Server' using the _maas._tcp service
    type where %s is the configured MAAS server name.
    """

    def __init__(self):
        self.service = None

    def maas_name_changed(self, sender, instance, created, **kwargs):
        """Signal callback called when the MAAS name changed."""
        self.publish()

    def publish(self):
        """Publish the maas_name.

        It will remove any previously published name first.
        """
        if self.service is not None:
            self.service.unpublish()

        site_name = "%s MAAS Server" % Config.objects.get_config('maas_name')
        self.service = ZeroconfService(
            name=site_name, port=80, stype="_maas._tcp")
        self.service.publish()


def setup_maas_avahi_service():
    """Register the MAASAvahiService() with the config changed signal."""
    service = MAASAvahiService()

    # Publish it first.
    service.publish()
    Config.objects.config_changed_connect(
        'maas_name', service.maas_name_changed)
