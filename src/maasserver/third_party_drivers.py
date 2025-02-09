# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Third party driver support.

The current implementation is limited in a number of ways:
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

from copy import deepcopy
import fnmatch

from formencode import ForEach
from formencode.validators import String

from provisioningserver.config import ConfigBase, ConfigMeta
from provisioningserver.utils.config import ByteString, Schema

"""
Here's a description of fields for each entry for a third_party_driver.

blacklist - The name of a module to blacklist when using this driver.
The driver will be blacklisted via the kernel command line during
installation, and via a modprobe.d entry afterwards.

comment - A comment string that will be added to the sources.list file
on the target.

key_binary - The public key for the repository in binary. Starting with a
binary gpg key file (NOT ascii armored) containing the key for a repository,
you can generate the key binary string like this:

>>>> import yaml
>>>> key_text = open('my_key.gpg').read()
>>>> print yaml.safe_dump(key_text)

NOTE: If you start off with an ascii armored key, you can convert it into
a binary key by importing it into a gpg keyring, then exporting it into
a file without using -a/--armor.

You can inspect a key from drivers.yaml by dumping it back into a file
and using gpg to manipulate it:

>>> import yaml
>>> drivers_config = yaml.safe_load(open('etc/maas/drivers.yaml').read())
>>> drivers_list = drivers_config['drivers']
>>> first_driver = drivers_list[0]
>>> open('some_key.gpg', 'w').write(first_driver['key_binary'])

$ gpg --import -n some_key.gpg
gpg: key CF700356: "Launchpad PPA for Some Driver" not changed
gpg: Total number processed: 1
gpg:              unchanged: 1

modaliases - The list of modaliases patterns to match when deciding when
to use this driver. MAAS collects modalias strings for nodes during
enlistment, and at install time, will compare those modalias strings to
the modalias patterns supplied for drivers.

module - The name of the kernel module to load on the target system.

repository - The URL of the repository to load packages from. The should
repository contain both deb and udeb packages for the driver.

series - List of Ubuntu series codenames to install the driver for.

packages - The name of the deb package to retrieve from the repository.
"""


class ConfigDriver(Schema):
    """Configuration validator for a driver."""

    if_key_missing = None

    blacklist = String()
    comment = String()
    key_binary = ByteString()
    modaliases = ForEach(String)
    module = String()
    package = String()
    repository = String()
    series = ForEach(String)


class DriversConfigMeta(ConfigMeta):
    """Meta-configuration for third party drivers."""

    envvar = "MAAS_THIRD_PARTY_DRIVER_SETTINGS"
    default = "drivers.yaml"


class DriversConfig(ConfigBase, Schema, metaclass=DriversConfigMeta):
    """Configuration for third party drivers."""

    if_key_missing = None

    drivers = ForEach(ConfigDriver)


def match_aliases_to_driver(detected_aliases, drivers):
    """Find the first driver that matches any supplied modalias."""
    for driver in drivers:
        for alias in driver["modaliases"]:
            matches = fnmatch.filter(detected_aliases, alias)
            if len(matches) > 0:
                return driver

    return None


def populate_kernel_opts(driver):
    """Create kernel option string from module blacklist."""
    blacklist = driver.get("blacklist")
    if blacklist is not None:
        driver["kernel_opts"] = "modprobe.blacklist=%s" % blacklist

    return driver


def get_third_party_driver(node, detected_aliases=None, series=""):
    """Determine which, if any, third party driver is required.

    Use the node's modaliases strings to determine if a third party
    driver is required.

    Drivers are filtered for the specified series.
    """
    if detected_aliases is None:
        detected_aliases = node.modaliases

    third_party_drivers_config = DriversConfig.load_from_cache()
    third_party_drivers = third_party_drivers_config["drivers"]

    matched_driver = match_aliases_to_driver(
        detected_aliases, third_party_drivers
    )

    if matched_driver is None:
        return {}

    available_series = matched_driver.get("series", [])
    if available_series and series not in available_series:
        return {}

    driver = deepcopy(matched_driver)
    driver = populate_kernel_opts(driver)
    return driver
