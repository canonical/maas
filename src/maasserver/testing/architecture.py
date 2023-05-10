# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for architectures in testing."""


from random import randint

from maasserver import forms
from maasserver.testing.factory import factory


def make_arch(
    with_subarch=True, arch_name=None, subarch_name=None, extra=None
):
    """Generate an arbitrary architecture name.

    :param with_subarch: Should the architecture include a slash and a
        sub-architecture name?  Defaults to `True`.
    """
    if arch_name is None:
        arch_name = factory.make_name("arch")
    if with_subarch:
        if subarch_name is None:
            subarch_name = factory.make_name("sub")
        result = f"{arch_name}/{subarch_name}"
    else:
        result = arch_name

    if not extra:
        extra = {}
    extra.setdefault("platform", "generic")
    extra.setdefault("supported_platforms", subarch_name)
    factory.make_default_ubuntu_release_bootable(arch_name, extra=extra)

    return result


def patch_usable_architectures(testcase, architectures=None):
    """Set a fixed list of usable architecture names.

    A usable architecture is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can use.
    :param architectures: Optional list of architecture names.  If omitted,
        defaults to a list (which may be empty) of random architecture names.
    """
    if architectures is None:
        architectures = [
            "{}/{}".format(factory.make_name("arch"), factory.make_name("sub"))
            for _ in range(randint(0, 2))
        ]
    patch = testcase.patch(forms, "list_all_usable_architectures")
    patch.return_value = architectures


def make_usable_architecture(
    testcase, with_subarch=True, arch_name=None, subarch_name=None, extra=None
):
    """Return arbitrary architecture name, and make it "usable."

    A usable architecture is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can pass to
        `patch_usable_architectures`.
    :param with_subarch: Should the architecture include a slash and a
        sub-architecture name?  Defaults to `True`.
    :param arch_name: The architecture name. Useful in cases where
        we need to test that not supplying an arch works correctly.
    :param subarch_name: The subarchitecture name. Useful in cases where
        we need to test that not supplying a subarch works correctly.
    """
    arch = make_arch(
        with_subarch=with_subarch,
        arch_name=arch_name,
        subarch_name=subarch_name,
        extra=extra,
    )
    patch_usable_architectures(testcase, [arch])
    return arch
