#!/usr/bin/env python3
# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

import sys

from provisioningserver import security
import provisioningserver.cluster_config_command
import provisioningserver.dns.commands.edit_named_options
import provisioningserver.dns.commands.get_named_conf
import provisioningserver.dns.commands.setup_dns
import provisioningserver.register_command
import provisioningserver.support_dump
import provisioningserver.upgrade_cluster
import provisioningserver.utils.arp
import provisioningserver.utils.avahi
import provisioningserver.utils.beaconing
import provisioningserver.utils.dhcp
import provisioningserver.utils.scan_network
from provisioningserver.utils.script import MainScript
import provisioningserver.utils.send_beacons

COMMON_COMMANDS = {
    "observe-arp": provisioningserver.utils.arp,
    "observe-beacons": provisioningserver.utils.beaconing,
    "observe-mdns": provisioningserver.utils.avahi,
    "observe-dhcp": provisioningserver.utils.dhcp,
    "send-beacons": provisioningserver.utils.send_beacons,
    "scan-network": provisioningserver.utils.scan_network,
    "setup-dns": provisioningserver.dns.commands.setup_dns,
    "get-named-conf": provisioningserver.dns.commands.get_named_conf,
    "edit-named-options": provisioningserver.dns.commands.edit_named_options,
}

RACK_ONLY_COMMANDS = {
    "check-for-shared-secret": security.CheckForSharedSecretScript,
    "config": provisioningserver.cluster_config_command,
    "install-shared-secret": security.InstallSharedSecretScript,
    "register": provisioningserver.register_command,
    "support-dump": provisioningserver.support_dump,
    "upgrade-cluster": provisioningserver.upgrade_cluster,
}


main = MainScript(__doc__)

commands = COMMON_COMMANDS.copy()

# If 'maas-common' isn't being executed, add rack-specific commands in addition
# to the generic set of commands.
if not sys.argv[0].endswith("/maas-common"):
    commands.update(RACK_ONLY_COMMANDS)

for name, command in sorted(commands.items()):
    main.register(name, command)
main()
