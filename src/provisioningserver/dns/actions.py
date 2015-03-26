# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level actions to manage the DNS service, like reloading zones."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "bind_reconfigure",
    "bind_reload",
    "bind_reload_zone",
    "bind_write_configuration",
    "bind_write_options",
    "bind_write_zones",
]

import collections
from subprocess import CalledProcessError
from time import sleep

from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    set_up_options_conf,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.shell import ExternalProcessError


maaslog = get_maas_logger("dns")


def bind_reconfigure():
    """Ask BIND to reload its configuration and *new* zone files.

    From rndc(8):

      Reload the configuration file and load new zones, but do not reload
      existing zone files even if they have changed. This is faster than a
      full reload when there is a large number of zones because it avoids the
      need to examine the modification times of the zones files.

    """
    try:
        execute_rndc_command(("reconfig",))
    except CalledProcessError as exc:
        maaslog.error("Reloading BIND configuration failed: %s", exc)
        # Log before upgrade so that the output does not go to maaslog.
        ExternalProcessError.upgrade(exc)
        raise


def bind_reload():
    """Ask BIND to reload its configuration and all zone files."""
    try:
        execute_rndc_command(("reload",))
    except CalledProcessError as exc:
        maaslog.error("Reloading BIND failed: %s", exc)
        # Log before upgrade so that the output does not go to maaslog.
        ExternalProcessError.upgrade(exc)
        raise


def bind_reload_with_retries(attempts=10, interval=2):
    """Ask BIND to reload its configuration and all zone files.

    :param attempts: The number of attempts.
    :param interval: The time in seconds to sleep between each attempt.
    """
    for countdown in xrange(attempts - 1, -1, -1):
        try:
            bind_reload()
        except CalledProcessError:
            if countdown == 0:
                raise
            else:
                sleep(interval)
        else:
            break


def bind_reload_zone(zone_name):
    """Ask BIND to reload the zone file for the given zone.

    :param zone_name: The name of the zone to reload.
    """
    try:
        execute_rndc_command(("reload", zone_name))
    except CalledProcessError as exc:
        maaslog.error("Reloading BIND zone %r failed: %s", zone_name, exc)
        # Log before upgrade so that the output does not go to maaslog.
        ExternalProcessError.upgrade(exc)
        raise


def bind_write_configuration(zones, trusted_networks):
    """Write BIND's configuration.

    :param zones: Those zones to include in main config.
    :type zones: Sequence of :py:class:`DNSZoneData`.

    :param trusted_networks: A sequence of CIDR network specifications that
        are permitted to use the DNS server as a forwarder.
    """
    # trusted_networks was formerly specified as a single IP address with
    # netmask. These assertions are here to prevent code that assumes that
    # slipping through.
    assert not isinstance(trusted_networks, (bytes, unicode))
    assert isinstance(trusted_networks, collections.Sequence)

    dns_config = DNSConfig(zones=zones)
    dns_config.write_config(trusted_networks=trusted_networks)


def bind_write_options(upstream_dns):
    """Write BIND options.

    :param upstream_dns: A sequence of upstream DNS servers.
    """
    # upstream_dns was formerly specified as a single IP address. These
    # assertions are here to prevent code that assumes that slipping through.
    assert not isinstance(upstream_dns, (bytes, unicode))
    assert isinstance(upstream_dns, collections.Sequence)

    set_up_options_conf(upstream_dns=upstream_dns)


def bind_write_zones(zones):
    """Write out DNS zones.

    :param zones: Those zones to write.
    :type zones: Sequence of :py:class:`DNSZoneData`.
    """
    for zone in zones:
        zone.write_config()
