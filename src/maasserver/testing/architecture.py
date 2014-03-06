# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for architectures in testing."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_usable_architecture',
    'patch_usable_architectures',
    ]

from random import randint

from maasserver import forms
from maasserver.testing.factory import factory


def make_arch(with_subarch=True):
    """Generate an arbitrary architecture name.

    :param with_subarch: Should the architecture include a slash and a
        sub-architecture name?  Defaults to `True`.
    """
    base_arch = factory.make_name('arch')
    if with_subarch:
        return '%s/%s' % (base_arch, factory.make_name('sub'))
    else:
        return base_arch


def patch_usable_architectures(testcase, architectures=None):
    """Set a fixed list of usable architecture names.

    A usable architecture is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can use.
    :param architectures: Optional list of architecture names.  If omitted,
        defaults to a list (which may be empty) of random architecture names.
    """
    if architectures is None:
        architectures = [
            "%s/%s" % (factory.make_name('arch'), factory.make_name('sub'))
            for _ in range(randint(0, 2))
            ]
    patch = testcase.patch(forms, 'list_all_usable_architectures')
    patch.return_value = architectures


def make_usable_architecture(testcase, with_subarch=True):
    """Return arbitrary architecture name, and make it "usable."

    A usable architecture is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can pass to
        `patch_usable_architectures`.
    :param with_subarch: Should the architecture include a slash and a
        sub-architecture name?  Defaults to `True`.
    """
    arch = make_arch(with_subarch=with_subarch)
    patch_usable_architectures(testcase, [arch])
    return arch
