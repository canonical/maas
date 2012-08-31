#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import provisioningserver.dhcp.writer
import provisioningserver.pxe.install_bootloader
import provisioningserver.pxe.install_image
from provisioningserver.utils import (
    AtomicWriteScript,
    MainScript,
    )


main = MainScript(__doc__)
main.register(
    "install-pxe-bootloader",
    provisioningserver.pxe.install_bootloader)
main.register(
    "install-pxe-image",
    provisioningserver.pxe.install_image)
main.register(
    "generate-dhcp-config",
    provisioningserver.dhcp.writer)
main.register(
    "atomic_write",
    AtomicWriteScript)
main()
