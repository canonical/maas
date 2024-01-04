# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the rack contoller (and possibly the region)."""
from typing import Any, Callable


def enum_choices(
    enum: Any, transform: Callable[[str], str] = lambda value: value
) -> tuple[[str, str], ...]:
    """Return sequence of tuples for Django's `choices` field from an enum-like class.

    Enum-like classes have the following structure:

      class MyEnum:
          VAL1 = "value1"
          VAL2 = "value2"

    Each element in a 2-tuple, with the enum value both as database value and
    human readable value (e.g. (("value1", "value1"), ("value2", "value2")) for
    the example above).

    If a `transform` callable is provided, it's called on the human-readable
    value to get a processed version.

    TODO:
      This should be dropped and classes become subclasses of django.db.models.TextChoices
      once we move to Django 3.0 which has native support for Enum types.
      The `choices` property of TextChoices replaces this function.
    """

    return tuple(
        (value, transform(value))
        for attr, value in enum.__dict__.items()
        if not attr.startswith("_")
    )


class CONTROLLER_INSTALL_TYPE:
    """MAAS controller install type."""

    UNKNOWN = ""
    SNAP = "snap"
    DEB = "deb"


CONTROLLER_INSTALL_TYPE_CHOICES = enum_choices(CONTROLLER_INSTALL_TYPE)


class MACVLAN_MODE:
    BRIDGE = "bridge"
    PASSTHRU = "passthru"
    PRIVATE = "private"
    VEPA = "vepa"


MACVLAN_MODE_CHOICES = enum_choices(MACVLAN_MODE)


class LIBVIRT_NETWORK:
    DEFAULT = "default"
    MAAS = "maas"


LIBVIRT_NETWORK_CHOICES = enum_choices(LIBVIRT_NETWORK)
