#!/usr/bin/env python2.7
# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Command-line interface for the MAAS provisioning component."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import os


def init_clusterd_db():
    CLUSTERD_DB_PATH = '/var/lib/maas/clusterd.db'
    print("init_clusterd_db")
    if not os.access(CLUSTERD_DB_PATH, os.W_OK):
        print("AHHAHAHAHA init_clusterd_db")
        from maascli.config import ProfileConfig
        
        with ProfileConfig.open(CLUSTERD_DB_PATH) as config:
          config['resource_root'] = '/var/lib/maas/boot-resources/current/'
          config['CLUSTER_UUID']="a25a9557-5525-4c5d-9d98-b7c414c62ffe"
          config['MAAS_URL']='http://localhost:5240/MAAS'


init_clusterd_db()


from provisioningserver import security
import provisioningserver.boot.install_bootloader
import provisioningserver.boot.install_grub
import provisioningserver.configure_maas_url
import provisioningserver.customize_config
import provisioningserver.dhcp.writer
import provisioningserver.upgrade_cluster
from provisioningserver.utils.script import (
    AtomicWriteScript,
    MainScript,
    )


script_commands = {
    'atomic-write': AtomicWriteScript,
    'check-for-shared-secret': security.CheckForSharedSecretScript,
    'configure-maas-url': provisioningserver.configure_maas_url,
    'customize-config': provisioningserver.customize_config,
    'generate-dhcp-config': provisioningserver.dhcp.writer,
    'install-shared-secret': security.InstallSharedSecretScript,
    'install-uefi-config': provisioningserver.boot.install_grub,
    'upgrade-cluster': provisioningserver.upgrade_cluster,
}


main = MainScript(__doc__)
for name, command in sorted(script_commands.items()):
    main.register(name, command)
main()
