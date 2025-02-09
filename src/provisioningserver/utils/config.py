# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# TODO: Description here.
"""Helpers for configuration validation.

Especially work-arounds for broken `formencode` behaviour.
"""

import os.path
import re
import uuid

import formencode


class ByteString(formencode.FancyValidator):
    """A FormEncode `ByteString` validator that works.

    The one in `formencode` is unmitigated crap.
    """

    not_empty = None
    accept_python = False
    messages = {
        "noneType": "The input must be a byte string (not None)",
        "badType": (
            "The input must be a byte string (not a %(type)s: %(value)r)"
        ),
    }

    def _validate(self, value, state=None):
        if not isinstance(value, bytes):
            raise formencode.Invalid(
                self.message(
                    "badType",
                    state,
                    value=value,
                    type=type(value).__qualname__,
                ),
                value,
                state,
            )

    _validate_python = _validate
    _validate_other = _validate

    def empty_value(self, value):
        return b""


class UnicodeString(formencode.FancyValidator):
    """A FormEncode `UnicodeString` validator that works.

    The one in `formencode` is... weird.
    """

    not_empty = None
    accept_python = False
    messages = {
        "noneType": "The input must be a Unicode string (not None)",
        "badType": (
            "The input must be a Unicode string (not a %(type)s: %(value)r)"
        ),
    }

    def _validate(self, value, state=None):
        if not isinstance(value, str):
            raise formencode.Invalid(
                self.message(
                    "badType",
                    state,
                    value=value,
                    type=type(value).__qualname__,
                ),
                value,
                state,
            )

    _validate_python = _validate
    _validate_other = _validate

    def empty_value(self, value):
        return ""


class UUIDString(formencode.FancyValidator):
    """A validator for UUIDs.

    The string must be a valid UUID.
    """

    accept_python = False
    messages = {"notUUID": "%(value)r Failed to parse UUID"}

    def _convert(self, value, state=None):
        if isinstance(value, uuid.UUID):
            return str(value)
        else:
            try:
                uuid.UUID(value)
            except Exception:
                raise formencode.Invalid(  # noqa: B904
                    self.message("notUUID", state, value=value), value, state
                )
            else:
                return value

    _convert_from_python = _convert
    _convert_to_python = _convert


class DirectoryString(formencode.FancyValidator):
    """A validator for a directory on the local filesystem.

    The directory must exist.
    """

    accept_python = False
    messages = {"notDir": "%(value)r does not exist or is not a directory"}

    def _validate_other(self, value, state=None):
        # Only validate on the way _in_; it's not the store's fault if it
        # contains a directory which has since been removed.
        if os.path.isdir(value):
            return value
        else:
            raise formencode.Invalid(
                self.message("notDir", state, value=value), value, state
            )


class ExtendedURL(formencode.validators.URL):
    """A validator URLs.

    This validator extends formencode.validators.URL by adding support
    for the general case of hostnames (i.e. hostnames containing numeric
    digits, hyphens, and hostnames of length 1), and ipv6 addresses with
    brackets.  (Brackets are required, because we allow ":port".)
    """

    # 2016-08-09 lamont There is a small over-acceptance here:  if there is a
    # :: in the ipv6 address, then it's possible to have more than 8 overall
    # groupings.  We'll catch that later on when we cannot convert it to an
    # ipv6 address, rather than individually handling all of the possible
    # combinations for ::-containing addresses.
    url_re = re.compile(
        r"""
        ^(http|https)://
        (?:[%:\w]*@)?                              # authenticator
        (?:                                        # ip or domain
        (?P<ip>(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}
            (?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))|
        (?P<ipv6>\[(?:
            ::ffff:(?:[0-9]+\.){3}(?:[0-9]+)|      # ipv6 form of ipv4 addr
            (?:(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4})|
            (?:(?:[a-fA-F0-9]{1,4}:){1,6}:
               (?:[a-fA-F0-9]{1,4}:){0,5}[a-fA-F0-9]{1,4})|
            ::[a-fA-F0-9]{1,4}|
            [a-fA-F0-9]{1,4}::)\])|
        (?P<domain>[a-z0-9][a-z0-9\-]{,62}\.)*     # subdomain
        (?P<tld>[a-zA-Z0-9]{1,63}|
            [a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])  # tld or hostname
        )
        (?::[0-9]{1,5})?                           # port
        # files/delims/etc
        (?P<path>/[a-z0-9\-\._~:/\?#\[\]@!%\$&\'\(\)\*\+,;=]*)?
        $
    """,
        re.IGNORECASE | re.VERBOSE,
    )


class Schema(formencode.Schema):
    """A FormEncode `Schema` that works.

    Work around a bug in `formencode` where it considers instances of `bytes`
    to be iterators, and so complains about multiple values.
    """

    def _value_is_iterator(self, value):
        if isinstance(value, bytes):
            return False
        else:
            return super()._value_is_iterator(value)


class OneWayStringBool(formencode.validators.StringBool):
    """A `StringBool` that doesn't convert a boolean back into a string.

    Used for "true" and "false" values, but doesn't convert a boolean back
    to a string.
    """

    def from_python(self, value):
        """Do nothing."""
        return value
