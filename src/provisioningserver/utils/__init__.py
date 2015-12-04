# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

__all__ = [
    "coerce_to_valid_hostname",
    "filter_dict",
    "flatten",
    "import_settings",
    "in_develop_mode",
    "locate_config",
    "parse_key_value_file",
    "ShellTemplate",
    "sudo",
    "typed",
    "warn_deprecated",
    "write_custom_config_section",
]

from collections import Iterable
from itertools import chain
import os
from pipes import quote
import sys
from sys import _getframe as getframe
from typing import Tuple
from warnings import warn

import tempita

# Use typecheck-decorator if it's available.
try:
    from maastesting.typecheck import typed
except ImportError:
    typed = lambda func: func


@typed
def locate_config(*path: Tuple[str]):
    """Return the location of a given config file or directory.

    :param path: Path elements to resolve relative to `${MAAS_ROOT}/etc/maas`.
    """
    # The `os.curdir` avoids a crash when `path` is empty.
    path = os.path.join(os.curdir, *path)
    if os.path.isabs(path):
        return path
    else:
        # Avoid circular imports.
        from provisioningserver.path import get_tentative_path
        return get_tentative_path("etc", "maas", path)


setting_expression = r"""
    ^([A-Z0-9_]+)    # Variable name is all caps, alphanumeric and _.
    =                # Assignment operator.
    (?:"|\')?        # Optional leading single or double quote.
    (.*)             # Value
    (?:"|\')?        # Optional trailing single or double quote.
    """


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
    return max(dict_depth(v, depth + 1) for _, v in d.items())


def split_lines(input, separator):
    """Split each item from `input` into a key/value pair."""
    return (line.split(separator, 1) for line in input if line.strip() != '')


def strip_pairs(input):
    """Strip whitespace of each key/value pair in input."""
    return ((key.strip(), value.strip()) for (key, value) in input)


def parse_key_value_file(file_name, separator=":"):
    """Parse a text file into a dict of key/value pairs.

    Use this for simple key:value or key=value files. There are no sections,
    as required for python's ConfigParse. Whitespace and empty lines are
    ignored, and it is assumed that the file is encoded as UTF-8.

    :param file_name: Name of file to parse.
    :param separator: The text that separates each key from its value.
    """
    with open(file_name, 'r', encoding="utf-8") as input:
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
        if isinstance(things, str):
            # String-like objects are treated as leaves; iterating through a
            # string yields more strings, each of which is also iterable, and
            # so on, until the heat-death of the universe.
            return iter((things,))
        elif isinstance(things, Iterable):
            # Recurse and merge in order to flatten nested structures.
            return chain.from_iterable(map(_flatten, things))
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


SYSTEMD_RUN_PATH = '/run/systemd/system'


def get_init_system():
    """Returns 'upstart' or 'systemd'."""
    if os.path.exists(SYSTEMD_RUN_PATH):
        return 'systemd'
    else:
        return 'upstart'
