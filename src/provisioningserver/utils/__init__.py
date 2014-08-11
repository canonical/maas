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
    "call_and_check",
    "compose_URL_on_IP",
    "create_node",
    "filter_dict",
    "import_settings",
    "locate_config",
    "parse_key_value_file",
    "ShellTemplate",
    "warn_deprecated",
    "write_custom_config_section",
    ]

import logging
import os
from pipes import quote
import string
import subprocess
from subprocess import CalledProcessError
import sys
from sys import _getframe as getframe
from urlparse import (
    urlparse,
    urlunparse,
    )
from warnings import warn

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
import bson
from lxml import etree
from netaddr import IPAddress
from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.cluster_config import get_maas_url
import simplejson as json
import tempita


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


def create_node(macs, arch, power_type, power_parameters):
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        raise Exception('Not creating node: no API key yet.')
    client = MAASClient(
        MAASOAuth(*api_credentials), MAASDispatcher(),
        get_maas_url())

    data = {
        'architecture': arch,
        'power_type': power_type,
        'power_parameters': json.dumps(power_parameters),
        'mac_addresses': macs,
        'autodetect_nodegroup': 'true'
    }
    url = '/api/1.0/nodes/'
    if node_exists(macs, url, client):
        return
    return client.post(url, 'new', **data)


# A table suitable for use with str.translate() to replace each
# non-printable and non-ASCII character in a byte string with a question
# mark, mimicking the "replace" strategy when encoding and decoding.
non_printable_replace_table = b"".join(
    chr(i) if chr(i) in string.printable else b"?"
    for i in xrange(0xff + 0x01))


class ExternalProcessError(CalledProcessError):
    """Raised when there's a problem calling an external command.

    Unlike `CalledProcessError`:

    - `__str__()` returns a string containing the output of the failed
      external process, if available. All non-printable and non-ASCII
      characters are filtered out, replaced by question marks.

    - `__unicode__()` is defined, and tries to return something
      analagous to `__str__()` but keeping in valid unicode characters
      from the error message.

    """

    @staticmethod
    def _to_unicode(string):
        if isinstance(string, bytes):
            return string.decode("ascii", "replace")
        else:
            return unicode(string)

    @staticmethod
    def _to_ascii(string, table=non_printable_replace_table):
        if isinstance(string, unicode):
            return string.encode("ascii", "replace")
        else:
            return bytes(string).translate(table)

    def __unicode__(self):
        cmd = u" ".join(quote(self._to_unicode(part)) for part in self.cmd)
        output = self._to_unicode(self.output)
        return u"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    def __str__(self):
        cmd = b" ".join(quote(self._to_ascii(part)) for part in self.cmd)
        output = self._to_ascii(self.output)
        return b"Command `%s` returned non-zero exit status %d:\n%s" % (
            cmd, self.returncode, output)

    @property
    def output_as_ascii(self):
        """The command's output as printable ASCII.

        Non-printable and non-ASCII characters are filtered out.
        """
        return self._to_ascii(self.output)

    @property
    def output_as_unicode(self):
        """The command's output as Unicode text.

        Invalid Unicode characters are filtered out.
        """
        return self._to_unicode(self.output)


def call_and_check(command, *args, **kwargs):
    """A wrapper around subprocess.check_call().

    :param command: Command line, as a list of strings.
    :return: The command's output from standard output.
    :raise ExternalProcessError: If the command returns nonzero.
    """
    process = subprocess.Popen(
        command, *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        **kwargs)
    stdout, stderr = process.communicate()
    stderr = stderr.strip()
    if process.returncode != 0:
        raise ExternalProcessError(process.returncode, command, output=stderr)
    return stdout


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


def is_compiled_xpath(xpath):
    """Is `xpath` a compiled expression?"""
    return isinstance(xpath, etree.XPath)


def is_compiled_doc(doc):
    """Is `doc` a compiled XPath document evaluator?"""
    return isinstance(doc, etree.XPathDocumentEvaluator)


def match_xpath(xpath, doc):
    """Return a match of expression `xpath` against document `doc`.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    is_xpath_compiled = is_compiled_xpath(xpath)
    is_doc_compiled = is_compiled_doc(doc)

    if is_xpath_compiled and is_doc_compiled:
        return doc(xpath.path)
    elif is_xpath_compiled:
        return xpath(doc)
    elif is_doc_compiled:
        return doc(xpath)
    else:
        return doc.xpath(xpath)


def try_match_xpath(xpath, doc, logger=logging):
    """See if the XPath expression matches the given XML document.

    Invalid XPath expressions are logged, and are returned as a
    non-match.

    :type xpath: Either `unicode` or `etree.XPath`
    :type doc: Either `etree._ElementTree` or `etree.XPathDocumentEvaluator`

    :rtype: bool
    """
    try:
        # Evaluating an XPath expression against a document with LXML
        # can return a list or a string, and perhaps other types.
        # Casting the return value into a boolean context appears to
        # be the most reliable way of detecting a match.
        return bool(match_xpath(xpath, doc))
    except etree.XPathEvalError as error:
        # Get a plaintext version of `xpath`.
        expr = xpath.path if is_compiled_xpath(xpath) else xpath
        logger.warning("Invalid expression '%s': %s", expr, unicode(error))
        return False


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


def compose_URL_on_IP(base_url, host):
    """Produce a URL referring to a host by IP address.

    This is straightforward if the IP address is an IPv4 address; but if it's
    an IPv6 address, the URL must contain the IP address in square brackets as
    per RFC 3986.

    :param base_url: URL without the host part, e.g. `http:///path'.
    :param host: IP address to insert in the host part of the URL.
    :return: A URL string with the host part taken from `host`, and all others
        from `base_url`.
    """
    if IPAddress(host).version == 6:
        netloc_host = '[%s]' % host
    else:
        netloc_host = host
    parsed_url = urlparse(base_url)
    if parsed_url.port is None:
        netloc = netloc_host
    else:
        netloc = '%s:%d' % (netloc_host, parsed_url.port)
    return urlunparse(parsed_url._replace(netloc=netloc))


def map_enum(enum_class):
    """Map out an enumeration class as a "NAME: value" dict."""
    # Filter out anything that starts with '_', which covers private and
    # special methods.  We can make this smarter later if we start using
    # a smarter enumeration base class etc.  Or if we switch to a proper
    # enum mechanism, this function will act as a marker for pieces of
    # code that should be updated.
    return {
        key: value
        for key, value in vars(enum_class).items()
        if not key.startswith('_')
    }


def map_enum_reverse(enum_class, ignore=None):
    """Like map_enum(), but reverse its keys and values so you can lookup
    text representations from the enum's integer value.

    Any values in `ignore` are left out of the returned dict.
    """
    if ignore is None:
        ignore = []
    return dict([
        (v, k) for k, v in map_enum(enum_class).viewitems()
        if k not in ignore])


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
