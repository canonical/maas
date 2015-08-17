#!/usr/bin/env python2.7
# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from provisioningserver import security
import provisioningserver.boot.install_bootloader
import provisioningserver.boot.install_grub
import provisioningserver.cluster_config_command
import provisioningserver.configure_maas_url
import provisioningserver.customize_config
import provisioningserver.dhcp.writer
import provisioningserver.upgrade_cluster
from provisioningserver.utils.script import (
    AtomicDeleteScript,
    AtomicWriteScript,
    MainScript,
)


script_commands = {
    'atomic-write': AtomicWriteScript,
    'atomic-delete': AtomicDeleteScript,
    'check-for-shared-secret': security.CheckForSharedSecretScript,
    'configure-maas-url': provisioningserver.configure_maas_url,
    'customize-config': provisioningserver.customize_config,
    'generate-dhcp-config': provisioningserver.dhcp.writer,
    'install-shared-secret': security.InstallSharedSecretScript,
    'install-uefi-config': provisioningserver.boot.install_grub,
    'upgrade-cluster': provisioningserver.upgrade_cluster,
    'config': provisioningserver.cluster_config_command,
}


main = MainScript(__doc__)
for name, command in sorted(script_commands.items()):
    main.register(name, command)
main()
