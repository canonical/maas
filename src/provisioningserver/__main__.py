#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import provisioningserver.customize_config
import provisioningserver.dhcp.writer
import provisioningserver.pxe.install_bootloader
import provisioningserver.pxe.install_image
import provisioningserver.start_cluster_controller
from provisioningserver.utils import (
    AtomicWriteScript,
    MainScript,
    )


script_commands = {
    'atomic-write': AtomicWriteScript,
    'customize-config': provisioningserver.customize_config,
    'generate-dhcp-config': provisioningserver.dhcp.writer,
    'install-pxe-bootloader': provisioningserver.pxe.install_bootloader,
    'install-pxe-image': provisioningserver.pxe.install_image,
    'start-cluster-controller': provisioningserver.start_cluster_controller,
}


main = MainScript(__doc__)
for name, command in sorted(script_commands.items()):
    main.register(name, command)
main()
