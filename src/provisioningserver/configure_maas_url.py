# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Management command: update `MAAS_URL`.

The MAAS cluster controller packaging calls this in order to set a new
"MAAS URL" (the URL where nodes and cluster controllers can reach the
region controller) in the cluster controller's configuration files.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'add_arguments',
    'run',
    ]

from functools import partial
import re
from urlparse import urlparse

from provisioningserver.utils.fs import (
    atomic_write,
    read_text_file,
)
from provisioningserver.utils.url import compose_URL


MAAS_CLUSTER_CONF = '/etc/maas/maas_cluster.conf'

PSERV_YAML = '/etc/maas/pserv.yaml'


def rewrite_config_file(path, line_filter, mode=0600):
    """Rewrite config file at `path` on a line-by-line basis.

    Reads the file at `path`, runs its lines through `line_filter`, and
    writes the result back to `path`.

    Newlines may not be exactly as they were.  A trailing newline is ensured.

    :param path: Path to the config file to be rewritten.
    :param line_filter: A callable which accepts a line of input text (without
        trailing newline), and returns the corresponding line of output text
        (also without trailing newline).
    :param mode: File access permissions for the newly written file.
    """
    input_lines = read_text_file(path).splitlines()
    output_lines = [line_filter(line) for line in input_lines]
    result = '%s\n' % '\n'.join(output_lines)
    atomic_write(result, path, mode=mode)


def update_maas_cluster_conf(url):
    """Update `MAAS_URL` in `/etc/maas/maas_cluster.conf`.

    This file contains a shell-style assignment of the `MAAS_URL`
    variable.  Its assigned value will be changed to `url`.
    """
    substitute_line = lambda line: (
        'MAAS_URL="%s"' % url
        if re.match('\s*MAAS_URL=', line)
        else line)
    rewrite_config_file(MAAS_CLUSTER_CONF, substitute_line, mode=0640)


def extract_host(url):
    """Return just the host part of `url`."""
    return urlparse(url).hostname


def substitute_pserv_yaml_line(new_host, line):
    match = re.match('(\s*generator:)\s+(\S*)(.*)$', line)
    if match is None:
        # Not the generator line.  Keep as-is.
        return line
    [head, input_url, tail] = match.groups()
    return "%s %s%s" % (head, compose_URL(input_url, new_host), tail)


def update_pserv_yaml(host):
    """Update `generator` in `/etc/maas/pserv.yaml`.

    This file contains a YAML line defining a `generator` URL.  The line must
    look something like::

        generator: http://10.9.8.7/MAAS/api/1.0/pxeconfig/

    The host part of the URL (in this example, `10.9.8.7`) will be replaced
    with the new `host`.  If `host` is an IPv6 address, this function will
    ensure that it is surrounded by square brackets.
    """
    substitute_line = partial(substitute_pserv_yaml_line, host)
    rewrite_config_file(PSERV_YAML, substitute_line, mode=0644)


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.add_argument(
        'maas_url', metavar='URL',
        help=(
            "URL where nodes and cluster controllers can reach the MAAS "
            "region controller."))


def run(args):
    """Update MAAS_URL setting in configuration files.

    For use by the MAAS packaging scripts.  Updates configuration files
    to reflect a new MAAS_URL setting.
    """
    update_maas_cluster_conf(args.maas_url)
    update_pserv_yaml(extract_host(args.maas_url))
