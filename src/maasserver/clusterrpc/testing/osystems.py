# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for osystem rpc testing."""


import random

from maasserver.testing.factory import factory


def make_rpc_release(
    name=None, requires_license_key=False, can_commission=False
):
    """Return operating system release that would be returned from the
    ListOperatingSystems RPC call."""
    if name is None:
        name = factory.make_name("release")
    return dict(
        name=name,
        title=name,
        requires_license_key=requires_license_key,
        can_commission=can_commission,
    )


def make_rpc_osystem(name=None, releases=None):
    """Return operating system that would be returned from the
    ListOperatingSystems RPC call."""
    if name is None:
        name = factory.make_name("os")
    if releases is None:
        releases = [make_rpc_release() for _ in range(3)]
    if len(releases) > 0:
        default_release = random.choice(releases)["name"]
        commissioning_releases = [
            release for release in releases if release["can_commission"]
        ]
        if len(commissioning_releases) > 0:
            default_commissioning_release = random.choice(
                commissioning_releases
            )["name"]
        else:
            default_commissioning_release = None
    else:
        default_release = None
        default_commissioning_release = None
    return dict(
        name=name,
        title=name,
        releases=releases,
        default_release=default_release,
        default_commissioning_release=default_commissioning_release,
    )
