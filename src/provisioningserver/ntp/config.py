# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP service configuration."""

from contextlib import nullcontext
from functools import partial
from itertools import dropwhile, groupby
import os
from os.path import exists
import re

from netaddr import AddrFormatError, IPAddress

from provisioningserver.path import get_data_path, get_maas_run_path
from provisioningserver.utils.fs import sudo_write_file

_NTP_CONF_NAME = "chrony/chrony.conf"
_NTP_MAAS_CONF_NAME = "chrony/maas.conf"
_NTP_SOCK_NAME = "chrony/chronyd.sock"
_NTP_PID_NAME = "chrony/chronyd.pid"
_NTP_DIR_NAME = "chrony"


def configure(servers, peers, offset):
    """Configure the local NTP server with the given time references.

    This writes new ``chrony.chrony.conf`` and ``chrony.maas.conf`` files,
    using ``sudo`` in production.

    :param servers: An iterable of server addresses -- IPv4, IPv6, hostnames
        -- to use as time references.
    :param peers: An iterable of peer addresses -- IPv4, IPv6, hostnames -- to
        use as time references.
    :param offset: A relative stratum within MAAS's world. A region controller
        would be 0 and a rack controller would be 1.
    """
    ntp_maas_conf = _render_ntp_maas_conf(servers, peers, offset)
    ntp_maas_conf_path = get_data_path("etc", _NTP_MAAS_CONF_NAME)
    sudo_write_file(
        ntp_maas_conf_path, ntp_maas_conf.encode("utf-8"), mode=0o644
    )
    ntp_conf = _render_ntp_conf(ntp_maas_conf_path)
    ntp_conf_path = get_data_path("etc", _NTP_CONF_NAME)
    sudo_write_file(ntp_conf_path, ntp_conf.encode("utf-8"), mode=0o644)


configure_region = partial(configure, offset=0)
configure_rack = partial(configure, offset=1)


def normalise_address(address):
    """Normalise an IP address into a form suitable for the `ntp` daemon.

    It seems to prefer non-mapped IPv4 addresses, for example. Hostnames are
    passed through.
    """
    try:
        address = IPAddress(address)
    except AddrFormatError:
        return address  # Hostname.
    else:
        if address.is_ipv4_mapped():
            return address.ipv4()
        else:
            return address


def _render_ntp_conf(includefile):
    """Render ``ntp.conf`` based on the existing configuration.

    This configuration includes the file named by `includefile`.
    """
    ntp_conf_path = get_data_path("etc", _NTP_CONF_NAME)
    if exists(ntp_conf_path):
        cm = open(ntp_conf_path, encoding="utf-8")
    else:
        cm = nullcontext([])
    with cm as fd:
        content = "".join(_render_ntp_conf_from_source(fd, includefile))
    return content


def _render_ntp_conf_from_source(lines, includefile):
    """Render the lines of a new ``ntp.conf`` from the given lines.

    :param lines: An iterable of lines from an existing ``ntp.conf``.
    :return: An iterable of lines.
    """
    lines = _disable_existing_pools_and_servers(lines)
    lines = _remove_maas_includefile_option(lines)
    lines = _clean_whitespace(lines)
    yield from lines  # Has trailing blank line.
    yield "include %s\n" % includefile


def _render_ntp_maas_conf(servers, peers, offset):
    """Render ``ntp.maas.conf`` for the given time references.

    :param servers: An iterable of server addresses -- IPv4, IPv6, hostnames
        -- to use as time references.
    :param peers: An iterable of peer addresses -- IPv4, IPv6, hostnames -- to
        use as time references.
    :param offset: A relative stratum used when calculating the stratum for
        orphan mode (https://chrony.tuxfamily.org/doc/3.2/chrony.conf.html).
    """
    lines = [
        "# MAAS NTP configuration.",
        # LP: #1789872 - Use hardware timestamps (on interfaces where it is
        # available).
        "hwtimestamp *",
    ]
    servers = map(normalise_address, servers)
    lines.extend(
        "%s %s iburst"
        % (("server" if isinstance(server, IPAddress) else "pool"), server)
        for server in servers
    )
    peers = map(normalise_address, peers)
    # Note: `xleave` is needed here in order to take advantage of the increased
    # accuracy that comes with enabling hardware timestamps.
    lines.extend("peer %s xleave" % peer for peer in peers)
    # Chrony provides a special 'orphan' mode that is compatible
    # with ntpd's 'tos orphan' mode. (see
    # https://chrony.tuxfamily.org/doc/devel/chrony.conf.html)
    lines.append(f"local stratum {offset + 8:d} orphan")
    # Chrony requires 'allow' option to specify which client IPs
    # or Networks can use it as a time source. For now, allow all
    # clients to be compatible to 'ntpd'. In the future, it would
    # be nice to limit this similarly to how we do proxy. (see
    # https://chrony.tuxfamily.org/doc/3.2/chrony.conf.html)
    lines.append("allow")

    if "SNAP" in os.environ:
        run_dir = get_maas_run_path()
        lines.append(f"dumpdir {run_dir / _NTP_DIR_NAME}")
        lines.append(f"pidfile {run_dir / _NTP_PID_NAME}")
        lines.append(f"bindcmdaddress {run_dir / _NTP_SOCK_NAME}")

    lines.append("")  # Add newline at end.
    return "\n".join(lines)


_re_pool_or_server = re.compile(r" ^ \s* (?: pool | server ) \b ", re.VERBOSE)


def _is_pool_or_server_option(line):
    """Predicate: does the given line represent a pool or server option?"""
    return _re_pool_or_server.match(line) is not None


def _disable_existing_pools_and_servers(lines):
    """Disable ``pool`` and ``server`` lines.

    This comments-out each uncommented ``pool`` or ``server`` lines and adds a
    comment that it was disabled by MAAS.

    :param lines: An iterable of lines.
    :return: An iterable of lines.
    """
    for line in lines:
        if _is_pool_or_server_option(line):
            yield "# %s  # Disabled by MAAS.\n" % line.strip()
        else:
            yield line


_re_maas_includefile = re.compile(
    r" ^ \s* include \s+ .* \b %s \b " % re.escape(_NTP_MAAS_CONF_NAME),
    re.VERBOSE,
)


def _is_maas_includefile_option(line):
    """Predicate: does the given line represent a include of a MAAS file?"""
    return _re_maas_includefile.match(line) is not None


def _remove_maas_includefile_option(lines):
    """Remove ``includefile`` lines referencing MAAS-managed files.

    :param lines: An iterable of lines.
    :return: An iterable of lines.
    """
    for line in lines:
        if not _is_maas_includefile_option(line):
            yield line


def _is_line_blank(line):
    """Predicate: is the given line either empty or all whitespace?"""
    return len(line) == 0 or line.isspace()


def _clean_whitespace(lines):
    """Remove leading blank lines then squash repeated blank lines.

    :param lines: An iterable of lines.
    :return: An iterable of lines.
    """
    lines = dropwhile(_is_line_blank, lines)
    for blank, lines in groupby(lines, _is_line_blank):  # noqa: B020
        if not blank:
            yield from lines
            yield "\n"
