# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level actions to manage the DNS service, like reloading zones."""

from collections.abc import Sequence
from subprocess import CalledProcessError, TimeoutExpired
from time import sleep

from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    get_nsupdate_key_path,
    set_up_options_conf,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.shell import ExternalProcessError, run_command

maaslog = get_maas_logger("dns")


MAAS_NSUPDATE_HOST = "localhost"


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


def bind_freeze_zone(zone=None, timeout=2):
    cmd = ("freeze",)  # freeze all zones
    if zone:
        cmd = ("freeze", zone)  # freeze one zone

    try:
        execute_rndc_command(cmd, timeout=timeout)
    except CalledProcessError as e:
        maaslog.error(
            f"Freezing {zone if zone else 'all zones'} for update failed"
        )
        ExternalProcessError.upgrade(e)
        raise
    except TimeoutExpired as e:
        maaslog.error(
            f"Freezing {zone if zone else 'all zones'} for update timed out"
        )
        ExternalProcessError.upgrade(e)
        raise


def bind_thaw_zone(zone=None, timeout=2):
    cmd = ("thaw",)  # thaw all zones
    if zone:
        cmd = ("thaw", zone)  # thaw one zone

    try:
        execute_rndc_command(cmd, timeout=timeout)
    except CalledProcessError as e:
        maaslog.error(
            f"Thawing {zone if zone else 'all zones'} for update failed"
        )
        ExternalProcessError.upgrade(e)
        raise
    except TimeoutExpired as e:
        maaslog.error(
            f"Thawing {zone if zone else 'all zones'} for update timed out"
        )
        ExternalProcessError.upgrade(e)
        raise


def bind_reload(timeout=2):
    """Ask BIND to reload its configuration and all zone files.  This operation
    is 'best effort' (with logging) as the server may not be running, and there
    is often no context for reporting.

    :return: True if success, False otherwise.
    """
    try:
        execute_rndc_command(("reload",), timeout=timeout)
        return True
    except CalledProcessError as exc:
        maaslog.error("Reloading BIND failed (is it running?): %s", exc)
        return False
    except TimeoutExpired as exc:
        maaslog.error("Reloading BIND timed out (is it locked?): %s", exc)
        return False


def bind_reload_with_retries(attempts=10, interval=2, timeout=2):
    """Ask BIND to reload its configuration and all zone files.

    :param attempts: The number of attempts.
    :param interval: The time in seconds to sleep between each attempt.
    """
    for countdown in range(attempts - 1, -1, -1):
        if bind_reload(timeout=timeout):
            break
        if countdown == 0:
            break
        else:
            sleep(interval)


def bind_reload_zones(zone_list):
    """Ask BIND to reload the zone file for the given zone.

    :param zone_list: A list of zone names to reload, or a single name as a
        string.
    :return: True if success, False otherwise.
    """
    ret = True
    if not isinstance(zone_list, list):
        zone_list = [zone_list]
    for name in zone_list:
        try:
            execute_rndc_command(("reload", name))
        except CalledProcessError as exc:
            maaslog.error(
                "Reloading BIND zone %r failed (is it running?): %s", name, exc
            )
            ret = False
    return ret


def bind_write_configuration(zones, trusted_networks, forwarded_zones=None):
    """Write BIND's configuration.

    :param zones: Those zones to include in main config.
    :type zones: Sequence of :py:class:`DomainData`.

    :param trusted_networks: A sequence of CIDR network specifications that
        are permitted to use the DNS server as a forwarder.
    """
    # trusted_networks was formerly specified as a single IP address with
    # netmask. These assertions are here to prevent code that assumes that
    # slipping through.
    assert not isinstance(trusted_networks, (bytes, str))
    assert isinstance(trusted_networks, Sequence)

    dns_config = DNSConfig(zones=zones, forwarded_zones=forwarded_zones)
    dns_config.write_config(trusted_networks=trusted_networks)


def bind_write_options(upstream_dns, dnssec_validation):
    """Write BIND options.

    :param upstream_dns: A sequence of upstream DNS servers.
    :param dnssec_validation: Whether to enable DNSSec.
    """
    # upstream_dns was formerly specified as a single IP address. These
    # assertions are here to prevent code that assumes that slipping through.
    assert not isinstance(upstream_dns, (bytes, str))
    assert isinstance(upstream_dns, Sequence)

    set_up_options_conf(
        upstream_dns=upstream_dns, dnssec_validation=dnssec_validation
    )


def bind_write_zones(zones):
    """Write out DNS zones.

    :param zones: Those zones to write.
    :type zones: Sequence of :py:class:`DomainData`.
    """
    for zone in zones:
        zone.write_config()


class NSUpdateCommand:
    executable = "nsupdate"

    def __init__(self, zone, updates, **kwargs):
        self._zone = zone
        self._updates = updates
        self._serial = kwargs.get("serial")
        self._zone_ttl = kwargs["ttl"]

    def _format_update(self, update):
        if update.operation == "DELETE":
            if update.answer:
                return f"update delete {update.name} {update.rectype} {update.answer}"
            return f"update delete {update.name} {update.rectype}"
        ttl = update.ttl
        if ttl is None:
            ttl = self._zone_ttl
        return (
            f"update add {update.name} {ttl} {update.rectype} {update.answer}"
        )

    def update(self, server_address=MAAS_NSUPDATE_HOST):
        stdin = [f"zone {self._zone}"] + [
            self._format_update(update) for update in self._updates
        ]
        if server_address:
            stdin = [f"server {server_address}"] + stdin

        if self._serial:
            stdin.append(
                f"update add {self._zone} {self._zone_ttl} SOA {self._zone}. nobody.example.com. {self._serial} 600 1800 604800 {self._zone_ttl}"
            )

        stdin.append("send\n")

        cmd = [self.executable, "-k", get_nsupdate_key_path()]
        if len(self._updates) > 1:
            cmd.append("-v")  # use TCP for bulk payloads

        try:
            run_command(*cmd, stdin="\n".join(stdin).encode("ascii"))
        except CalledProcessError as exc:
            maaslog.error(f"dynamic update of DNS failed: {exc}")
            ExternalProcessError.upgrade(exc)
            raise
