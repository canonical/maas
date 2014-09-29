# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Code to generate `udev` rules."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'compose_network_interfaces_udev_rules',
    ]

from textwrap import dedent


def compose_udev_equality(key, value):
    """Return a udev comparison clause, like `ACTION=="add"`."""
    assert key == key.upper()
    return '%s=="%s"' % (key, value)


def compose_udev_attr_equality(attribute, value):
    """Return a udev attribute comparison clause, like `ATTR{type}=="1"`."""
    assert attribute == attribute.lower()
    return 'ATTR{%s}=="%s"' % (attribute, value)


def compose_udev_setting(key, value):
    """Return a udev assignment clause, like `NAME="eth0"`."""
    assert key == key.upper()
    return '%s="%s"' % (key, value)


def compose_udev_rule(interface, mac):
    """Return a udev rule to set the name of network interface with `mac`.

    The rule ends up as a single line looking something like:

        SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*",
        ATTR{address}="ff:ee:dd:cc:bb:aa", NAME="eth0"

    (Note the difference between `=` and `==`: they both occur.)
    """
    rule = ', '.join([
        compose_udev_equality('SUBSYSTEM', 'net'),
        compose_udev_equality('ACTION', 'add'),
        compose_udev_equality('DRIVERS', '?*'),
        compose_udev_attr_equality('address', mac),
        compose_udev_setting('NAME', interface),
        ])
    return '%s\n' % rule


def compose_network_interfaces_udev_rules(interfaces):
    """Return text for a udev persistent-net rules file.

    These rules assign fixed names to network interfaces.  They ensure that
    the same network interface cards come up with the same interface names on
    every boot.  Otherwise, the kernel may assign interface names in different
    orders on every boot, and so network interfaces can "switch identities"
    every other time the machine reboots.

    :param interfaces: List of tuples of interface name and MAC address.
    :return: Text to write into a udev rules file.
    """
    rules = [
        compose_udev_rule(interface, mac)
        for interface, mac in interfaces
        ]
    return dedent("""\
        # MAAS-assigned network interface names.
        %s
        # End of MAAS-assigned network interface names.
        """) % '\n\n'.join(rules)
