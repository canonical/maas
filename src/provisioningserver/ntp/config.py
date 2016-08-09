# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP service configuration."""

__all__ = [
    "configure",
]

from itertools import (
    dropwhile,
    groupby,
)
import re

from provisioningserver.path import get_path
from provisioningserver.utils.fs import sudo_write_file


_ntp_conf_name = "ntp.conf"
_ntp_maas_conf_name = "ntp.maas.conf"


def configure(servers):
    """Configure the local NTP server with the given time references.

    This writes new ``ntp.conf`` and ``ntp.maas.conf`` files, using ``sudo``
    in production.

    :param servers: An iterable of server addresses -- IPv4, IPv6, hostnames
        -- to use as time references.
    """
    ntp_maas_conf = _render_ntp_maas_conf(servers).encode("ascii")
    ntp_maas_conf_path = get_path("etc", _ntp_maas_conf_name)
    sudo_write_file(ntp_maas_conf_path, ntp_maas_conf, mode=0o644)
    ntp_conf = _render_ntp_conf(ntp_maas_conf_path).encode("ascii")
    ntp_conf_path = get_path("etc", _ntp_conf_name)
    sudo_write_file(ntp_conf_path, ntp_conf, mode=0o644)


def _render_ntp_conf(includefile):
    """Render ``ntp.conf`` based on the existing configuration.

    This configuration includes the file named by `includefile`.
    """
    ntp_conf_path = get_path("etc", _ntp_conf_name)
    with open(ntp_conf_path, "r", encoding="ascii") as fd:
        lines = _render_ntp_conf_from_source(fd, includefile)
        return "".join(lines)


def _render_ntp_conf_from_source(lines, includefile):
    """Render the lines of a new ``ntp.conf`` from the given lines.

    :param lines: An iterable of lines from an existing ``ntp.conf``.
    :return: An iterable of lines.
    """
    lines = _disable_existing_pools_and_servers(lines)
    lines = _remove_maas_includefile_option(lines)
    lines = _clean_whitespace(lines)
    yield from lines  # Has trailing blank line.
    yield "includefile %s\n" % includefile


def _render_ntp_maas_conf(servers):
    """Render ``ntp.maas.conf`` for the given time references.

    :param servers: An iterable of server addresses -- IPv4, IPv6, hostnames
        -- to use as time references.
    """
    lines = ["# MAAS NTP configuration."]
    lines.extend("server " + server for server in servers)
    return "\n".join(lines)


_re_pool_or_server = re.compile(
    r" ^ \s* (?: pool | server ) \b ",
    re.VERBOSE)


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
    r" ^ \s* includefile \s+ .* \b %s \b " % re.escape(_ntp_maas_conf_name),
    re.VERBOSE)


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
    for blank, lines in groupby(lines, _is_line_blank):
        if not blank:
            yield from lines
            yield "\n"
