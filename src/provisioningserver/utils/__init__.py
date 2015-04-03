# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    "create_node",
    "commission_node",
    "filter_dict",
    "flatten",
    "get_cluster_config",
    "import_settings",
    "locate_config",
    "parse_key_value_file",
    "ShellTemplate",
    "warn_deprecated",
    "write_custom_config_section",
    "in_develop_mode",
    "sudo",
]

from collections import Iterable
from itertools import (
    chain,
    imap,
)
import os
from pipes import quote
import re
import sys
from sys import _getframe as getframe
from warnings import warn

import bson
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NoConnectionsAvailable,
    NodeAlreadyExists,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    pause,
    retries,
)
import simplejson as json
import tempita
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)
from twisted.protocols.amp import UnhandledCommand


maaslog = get_maas_logger("utils")


def node_exists(macs, url, client):
    decoders = {
        "application/json": lambda data: json.loads(data),
        "application/bson": lambda data: bson.BSON(data).decode(),
    }
    params = {
        'mac_address': macs
    }
    response = client.get(url,
                          op='list',
                          **params)
    content = response.read()
    content_type = response.headers.gettype()
    decode = decoders[content_type]
    content = decode(content)
    return len(content) > 0


@asynchronous
@inlineCallbacks
def create_node(macs, arch, power_type, power_parameters, hostname=None):
    """Create a Node on the region and return its system_id.

    :param macs: A list of MAC addresses belonging to the node.
    :param arch: The node's architecture, in the form 'arch/subarch'.
    :param power_type: The node's power type as a string.
    :param power_parameters: The power parameters for the node, as a
        dict.
    """
    # Avoid circular dependencies.
    from provisioningserver.rpc.region import CreateNode
    from provisioningserver.cluster_config import get_cluster_uuid

    for elapsed, remaining, wait in retries(15, 5, reactor):
        try:
            client = getRegionClient()
            break
        except NoConnectionsAvailable:
            yield pause(wait, reactor)
    else:
        maaslog.error(
            "Can't create node, no RPC connection to region.")
        return

    # De-dupe the MAC addresses we pass. We sort here to avoid test
    # failures.
    macs = sorted(set(macs))
    try:
        response = yield client(
            CreateNode,
            cluster_uuid=get_cluster_uuid(),
            architecture=arch,
            power_type=power_type,
            power_parameters=json.dumps(power_parameters),
            mac_addresses=macs,
            hostname=hostname)
    except NodeAlreadyExists:
        # The node already exists on the region, so we log the error and
        # give up.
        maaslog.error(
            "A node with one of the mac addressess in %s already exists.",
            macs)
        returnValue(None)
    except UnhandledCommand:
        # The region hasn't been upgraded to support this method
        # yet, so give up.
        maaslog.error(
            "Unable to create node on region: Region does not "
            "support the CreateNode RPC method.")
        returnValue(None)
    else:
        returnValue(response['system_id'])


@asynchronous
@inlineCallbacks
def commission_node(system_id, user):
    """Commission a Node on the region.

    :param system_id: system_id of node to commission.
    :param user: user for the node.
    """
    # Avoid circular dependencies.
    from provisioningserver.rpc.region import CommissionNode

    for elapsed, remaining, wait in retries(15, 5, reactor):
        try:
            client = getRegionClient()
            break
        except NoConnectionsAvailable:
            yield pause(wait, reactor)
    else:
        maaslog.error(
            "Can't commission node, no RPC connection to region.")
        return

    try:
        yield client(
            CommissionNode,
            system_id=system_id,
            user=user)
    except CommissionNodeFailed as e:
        # The node cannot be commissioned, give up.
        maaslog.error(
            "Could not commission with system_id %s because %s.",
            system_id, e.args[0])
    except UnhandledCommand:
        # The region hasn't been upgraded to support this method
        # yet, so give up.
        maaslog.error(
            "Unable to commission node on region: Region does not "
            "support the CommissionNode RPC method.")
    finally:
        returnValue(None)


def locate_config(*path):
    """Return the location of a given config file or directory.

    Defaults to `/etc/maas` (followed by any further path elements you
    specify), but can be overridden using the `MAAS_CONFIG_DIR` environment
    variable.  (When running from a branch, this variable will point to the
    `etc/maas` inside the branch.)

    The result is absolute and normalized.
    """
    # Check for MAAS_CONFIG_DIR.  Count empty string as "not set."
    env_setting = os.getenv('MAAS_CONFIG_DIR', '')
    if env_setting == '':
        # Running from installed package.  Config is in /etc/maas.
        config_dir = '/etc/maas'
    else:
        # Running from branch or other customized setup.  Config is at
        # $MAAS_CONFIG_DIR/etc/maas.
        config_dir = env_setting

    return os.path.abspath(os.path.join(config_dir, *path))


setting_expression = r"""
    ^([A-Z0-9_]+)    # Variable name is all caps, alphanumeric and _.
    =                # Assignment operator.
    (?:"|\')?        # Optional leading single or double quote.
    (.*)             # Value
    (?:"|\')?        # Optional trailing single or double quote.
    """


def get_cluster_config(config_path):
    contents = open(config_path).read()

    results = re.findall(
        setting_expression, contents, re.MULTILINE | re.VERBOSE)

    return dict(results)


def find_settings(whence):
    """Return settings from `whence`, which is assumed to be a module."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: Put this in a shared
    # location.  It's currently duplicated from elsewhere.
    return {
        name: value
        for name, value in vars(whence).items()
        if not name.startswith("_")
    }


def import_settings(whence):
    """Import settings from `whence` into the caller's global scope."""
    # XXX 2012-10-11 JeroenVermeulen, bug=1065456: Put this in a shared
    # location.  It's currently duplicated from elsewhere.
    source = find_settings(whence)
    target = sys._getframe(1).f_globals
    target.update(source)


def filter_dict(dictionary, desired_keys):
    """Return a version of `dictionary` restricted to `desired_keys`.

    This is like a set union, except the values from `dictionary` come along.
    (Actually `desired_keys` can be a `dict`, but its values will be ignored).
    """
    return {
        key: value
        for key, value in dictionary.items()
        if key in desired_keys
    }


def dict_depth(d, depth=0):
    """Returns the max depth of a dictionary."""
    if not isinstance(d, dict) or not d:
        return depth
    return max(dict_depth(v, depth + 1) for _, v in d.iteritems())


def split_lines(input, separator):
    """Split each item from `input` into a key/value pair."""
    return (line.split(separator, 1) for line in input if line.strip() != '')


def strip_pairs(input):
    """Strip whitespace of each key/value pair in input."""
    return ((key.strip(), value.strip()) for (key, value) in input)


def parse_key_value_file(file_name, separator=":"):
    """Parse a text file into a dict of key/value pairs.

    Use this for simple key:value or key=value files. There are no
    sections, as required for python's ConfigParse. Whitespace and empty
    lines are ignored.

    :param file_name: Name of file to parse.
    :param separator: The text that separates each key from its value.
    """
    with open(file_name, 'rb') as input:
        return dict(strip_pairs(split_lines(input, separator)))


# Header and footer comments for MAAS custom config sections, as managed
# by write_custom_config_section.
maas_custom_config_markers = (
    "## Begin MAAS settings.  Do not edit; MAAS will overwrite this section.",
    "## End MAAS settings.",
)


def find_list_item(item, in_list, starting_at=0):
    """Return index of `item` in `in_list`, or None if not found."""
    try:
        return in_list.index(item, starting_at)
    except ValueError:
        return None


def write_custom_config_section(original_text, custom_section):
    """Insert or replace a custom section in a configuration file's text.

    This allows you to rewrite configuration files that are not owned by
    MAAS, but where MAAS will have one section for its own settings.  It
    doesn't read or write any files; this is a pure text operation.

    Appends `custom_section` to the end of `original_text` if there was no
    custom MAAS section yet.  Otherwise, replaces the existing custom MAAS
    section with `custom_section`.  Returns the new text.

    Assumes that the configuration file's format accepts lines starting with
    hash marks (#) as comments.  The custom section will be bracketed by
    special marker comments that make it clear that MAAS wrote the section
    and it should not be edited by hand.

    :param original_text: The config file's current text.
    :type original_text: unicode
    :param custom_section: Custom config section to insert.
    :type custom_section: unicode
    :return: New config file text.
    :rtype: unicode
    """
    header, footer = maas_custom_config_markers
    lines = original_text.splitlines()
    header_index = find_list_item(header, lines)
    if header_index is not None:
        footer_index = find_list_item(footer, lines, header_index)
        if footer_index is None:
            # There's a header but no footer.  Pretend we didn't see the
            # header; just append a new custom section at the end.  Any
            # subsequent rewrite will replace the part starting at the
            # header and ending at the header we will add here.  At that
            # point there will be no trace of the strange situation
            # left.
            header_index = None

    if header_index is None:
        # There was no MAAS custom section in this file.  Append it at
        # the end.
        lines += [
            header,
            custom_section,
            footer,
        ]
    else:
        # There is a MAAS custom section in the file.  Replace it.
        lines = (
            lines[:(header_index + 1)] +
            [custom_section] +
            lines[footer_index:])

    return '\n'.join(lines) + '\n'


class Safe:
    """An object that is safe to render as-is."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "<%s %r>" % (
            self.__class__.__name__, self.value)


def escape_py_literal(string):
    """Escape and quote a string for use as a python literal."""
    return repr(string).decode('ascii')


class ShellTemplate(tempita.Template):
    """A Tempita template specialised for writing shell scripts.

    By default, substitutions will be escaped using `pipes.quote`, unless
    they're marked as safe. This can be done using Tempita's filter syntax::

      {{foobar|safe}}

    or as a plain Python expression::

      {{safe(foobar)}}

    """

    default_namespace = dict(
        tempita.Template.default_namespace,
        safe=Safe)

    def _repr(self, value, pos):
        """Shell-quote the value by default."""
        rep = super(ShellTemplate, self)._repr
        if isinstance(value, Safe):
            return rep(value.value, pos)
        else:
            return quote(rep(value, pos))


def classify(func, subjects):
    """Classify `subjects` according to `func`.

    Splits `subjects` into two lists: one for those which `func`
    returns a truth-like value, and one for the others.

    :param subjects: An iterable of `(ident, subject)` tuples, where
        `subject` is an argument that can be passed to `func` for
        classification.
    :param func: A function that takes a single argument.

    :return: A ``(matched, other)`` tuple, where ``matched`` and
        ``other`` are `list`s of `ident` values; `subject` values are
        not returned.
    """
    matched, other = [], []
    for ident, subject in subjects:
        bucket = matched if func(subject) else other
        bucket.append(ident)
    return matched, other


def warn_deprecated(alternative=None):
    """Issue a `DeprecationWarning` for the calling function.

    :param alternative: Text describing an alternative to using this
        deprecated function.
    """
    target = getframe(1).f_code.co_name
    message = "%s is deprecated" % target
    if alternative is None:
        message = "%s." % (message,)
    else:
        message = "%s; %s" % (message, alternative)
    warn(message, DeprecationWarning, 1)


def flatten(*things):
    """Recursively flatten iterable parts of `things`.

    For example::

      >>> sorted(flatten([1, 2, {3, 4, (5, 6)}]))
      [1, 2, 3, 4, 5, 6]

    :return: An iterator.
    """
    def _flatten(things):
        if isinstance(things, basestring):
            # String-like objects are treated as leaves; iterating through a
            # string yields more strings, each of which is also iterable, and
            # so on, until the heat-death of the universe.
            return iter((things,))
        elif isinstance(things, Iterable):
            # Recurse and merge in order to flatten nested structures.
            return chain.from_iterable(imap(_flatten, things))
        else:
            # This is a leaf; return an single-item iterator so that it can be
            # chained with any others.
            return iter((things,))

    return _flatten(things)


def is_true(value):
    if value is None:
        return False
    return value.lower() in ("yes", "true", "t", "1")


def in_develop_mode():
    """Return True if `MAAS_CLUSTER_DEVELOP` environment variable is true."""
    return is_true(os.getenv('MAAS_CLUSTER_DEVELOP', None))


def sudo(command_args):
    """Wrap the command arguments in a sudo command, if not in debug mode."""
    if in_develop_mode():
        return command_args
    else:
        return ['sudo', '-n'] + command_args
