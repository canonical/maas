# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Enumerations meaningful to the rack contoller (and possibly the region)."""


# *** IMPORTANT ***
# Note to all ye who enter here: comments beginning with #: are special
# to Sphinx. They are extracted and form part of the documentation of
# the field they directly precede.


class MACVLAN_MODE:

    BRIDGE = "bridge"
    PASSTHRU = "passthru"
    PRIVATE = "private"
    VEPA = "vepa"


MACVLAN_MODE_CHOICES = (
    (MACVLAN_MODE.BRIDGE, "bridge"),
    (MACVLAN_MODE.PASSTHRU, "passthru"),
    (MACVLAN_MODE.PRIVATE, "private"),
    (MACVLAN_MODE.VEPA, "vepa"),
)


class LIBVIRT_NETWORK:

    DEFAULT = "default"
    MAAS = "maas"


LIBVIRT_NETWORK_CHOICES = (
    (LIBVIRT_NETWORK.DEFAULT, "default"),
    (LIBVIRT_NETWORK.MAAS, "maas"),
)
