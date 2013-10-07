# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for boot-image parameters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'make_boot_image_params',
    ]

from maastesting.factory import factory


def make_boot_image_params():
    """Create an arbitrary dict of boot-image parameters.

    These are the parameters that together describe a kind of boot that we
    may need a kernel and initrd for: architecture, sub-architecture,
    Ubuntu release, and boot purpose.  See the `tftppath` module for how
    these fit together.
    """
    return dict(
        architecture=factory.make_name('architecture'),
        subarchitecture=factory.make_name('subarchitecture'),
        release=factory.make_name('release'),
        purpose=factory.make_name('purpose'))
