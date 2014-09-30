# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration relating to concurrency in the cluster controller.

This module is intended as a place to define concurrency policies for code
running in the cluster controller. Typically this will take the form of a
Twisted concurrency primative, like `DeferredLock` or `DeferredSemaphore`.

"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "boot_images",
    "dhcp",
]

from twisted.internet.defer import DeferredLock

# Limit boot image imports to one at a time.
boot_images = DeferredLock()

# Limit DHCP changes to one at a time.
dhcp = DeferredLock()
