# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Third party driver support.

The current implementation is limited in a number of ways.

- Third party driver locations are currently hardcoded. Eventually,
  they will be fetched from a stream.
- Only one third party driver can be matched per system.
- Only on module, package, and blacklisted module can be configured
  per system.
- udeb fetching will only work if there is one driver per repository.
  There can be multiple versions of the udeb, but not udebs for multiple
  drivers.
- Third party drivers are only used for debian installer installations,
  not for commissioning or fastpath installations.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_third_party_driver',
    ]

from copy import deepcopy
import fnmatch

from metadataserver.models import commissioningscript


"""
The third_party_drivers dict field below is hardcoded now, but
eventually will be pulled from an external source.

Here's a description of fields for each entry.

blacklist - The name of a module to blacklist when using this driver.
The driver will be blacklisted via the kernel command line during
installation, and via a modprobe.d entry afterwards.

comment - A comment string that will be added to the sources.list file
on the target.

key - The URL to the public key for the repository.

modaliases - The list of modaliases patterns to match when deciding when
to use this driver. MAAS collects modalias strings for nodes during
enlistment, and at install time, will compare those modalias strings to
the modalias patterns supplied for drivers.

module - The name of the kernel module to load on the target system.

repository - The URL of the repository to load packages from. The should
repository contain both deb and udeb packages for the driver.

packages - The name of the deb package to retrieve from the repository.
"""

third_party_drivers = [
    {
        'blacklist': 'ahci',
        'comment': 'HPVSA driver',
        'key': ('http://keyserver.ubuntu.com/pks/lookup?search='
                '0x509C5B70C2755E20F737DC27933312C3CF700356&op=get'),
        'modaliases': [
            'pci:v00001590d00000047sv00001590sd00000047bc*sc*i*',
            'pci:v00001590d00000045sv00001590sd00000045bc*sc*i*',
            'pci:v00008086d00001D04sv00001590sd00000048bc*sc*i*',
            'pci:v00008086d00008C04sv00001590sd00000084bc*sc*i*',
            'pci:v00008086d00008C06sv00001590sd00000084bc*sc*i*',
            'pci:v00008086d00001C04sv00001590sd0000006Cbc*sc*i*',
        ],
        'module': 'hpvsa',
        'repository':
        'http://ppa.launchpad.net/hp-iss-team/hpvsa-update/ubuntu',
        'package': 'hpvsa',
    },
]


def node_modaliases(node):
    """Return a list of modaliases from the node."""
    name = commissioningscript.LIST_MODALIASES_OUTPUT_NAME
    query = node.nodecommissionresult_set.filter(name__exact=name)

    if len(query) == 0:
        return []

    results = query.first().data
    return results.splitlines()


def match_aliases_to_driver(detected_aliases, drivers):
    """Find the first driver that matches any supplied modalias."""
    for driver in drivers:
        for alias in driver['modaliases']:
            matches = fnmatch.filter(detected_aliases, alias)
            if len(matches) > 0:
                return driver

    return None


def populate_kernel_opts(driver):
    """Create kernel option string from module blacklist."""
    blacklist = driver.get('blacklist')
    if blacklist is not None:
        driver['kernel_opts'] = 'modprobe.blacklist=%s' % blacklist

    return driver


def get_third_party_driver(node):
    """Determine which, if any, third party driver is required.

    Use the node's modaliases strings to determine if a third party
    driver is required.
    """
    detected_aliases = node_modaliases(node)
    matched_driver = match_aliases_to_driver(detected_aliases,
                                             third_party_drivers)

    if matched_driver is None:
        return dict()

    driver = deepcopy(matched_driver)
    driver = populate_kernel_opts(driver)

    return driver
