#!/usr/bin/env python3.5
# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from provisioningserver import security
import provisioningserver.boot.install_grub
import provisioningserver.cluster_config_command
import provisioningserver.register_command
import provisioningserver.support_dump
import provisioningserver.upgrade_cluster
import provisioningserver.utils.arp
import provisioningserver.utils.avahi
import provisioningserver.utils.dhcp
import provisioningserver.utils.scan_network
from provisioningserver.utils.script import (
    AtomicDeleteScript,
    AtomicWriteScript,
    MainScript,
)


script_commands = {
    'atomic-write': AtomicWriteScript,
    'atomic-delete': AtomicDeleteScript,
    'check-for-shared-secret': security.CheckForSharedSecretScript,
    'config': provisioningserver.cluster_config_command,
    'install-shared-secret': security.InstallSharedSecretScript,
    'install-uefi-config': provisioningserver.boot.install_grub,
    'observe-arp': provisioningserver.utils.arp,
    'observe-mdns': provisioningserver.utils.avahi,
    'observe-dhcp': provisioningserver.utils.dhcp,
    'scan-network': provisioningserver.utils.scan_network,
    'register': provisioningserver.register_command,
    'support-dump': provisioningserver.support_dump,
    'upgrade-cluster': provisioningserver.upgrade_cluster,
}


main = MainScript(__doc__)
for name, command in sorted(script_commands.items()):
    main.register(name, command)
main()
