# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enum-related utilities."""


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
        if not key.startswith("_")
    }


def map_enum_unique_values(enum_class):
    """Map out an enumeration class as a "NAME: value" dict, but only include
    unique values in the enum."""
    values_seen = set()
    values = dict()
    for key, value in vars(enum_class).items():
        if value not in values_seen and not key.startswith("_"):
            values[key] = value
        values_seen.add(value)
    return values


def map_enum_reverse(enum_class, ignore=None):
    """Map out an enumeration class as a "value: NAME" dict.

    Works like `map_enum`, but reverse its keys and values so that you can
    look up text representations from the enum's integer value.

    Any keys in `ignore` are left out of the returned dict.  This lets you
    remove the `DEFAULT` entry that some enum classes have.
    """
    if ignore is None:
        ignore = []
    return {
        value: key
        for key, value in map_enum(enum_class).items()
        if key not in ignore
    }
