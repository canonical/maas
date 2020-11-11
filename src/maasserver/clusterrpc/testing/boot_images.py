# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for boot image rpc testing."""


from maasserver.testing.factory import factory


def make_rpc_boot_image(
    osystem=None,
    release=None,
    architecture=None,
    subarchitecture=None,
    label=None,
    purpose=None,
    xinstall_type=None,
    xinstall_path=None,
):
    """Return boot image that would be returned from a ListBootImages RPC call."""
    if osystem is None:
        osystem = factory.make_name("os")
    if release is None:
        release = factory.make_name("series")
    if architecture is None:
        architecture = factory.make_name("arch")
    if subarchitecture is None:
        subarchitecture = factory.make_name("subarch")
    if label is None:
        label = factory.make_name("label")
    if purpose is None:
        purpose = factory.make_name("purpose")
    if xinstall_type is None:
        xinstall_type = factory.make_name("xi_type")
    if xinstall_path is None:
        xinstall_path = factory.make_name("xi_path")
    return {
        "osystem": osystem,
        "release": release,
        "architecture": architecture,
        "subarchitecture": subarchitecture,
        "label": label,
        "purpose": purpose,
        "xinstall_type": xinstall_type,
        "xinstall_path": xinstall_path,
    }
