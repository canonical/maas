# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Hardware Drivers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
    )


class HardwareDriver:
    """A rough skeleton for a hardware driver.

    Lots remains to be determined: this is a guide, not a prescription.
    However, three methods stand out:

    * ``getControlContext``

    * ``getResourceContext``

    * ``getDiscoveryContext``

    Many drivers will undoubtedly share the IPMI control implementation,
    but may have quite different boot resource requirements, or a
    proprietary discovery agent. Dividing responsibilities at this level
    seems to be about right for modularity. We'll learn more as this
    feature develops.

    We also need a way to map to this into the RPC space, which is flat,
    and does not have accomodation for maintaining object references
    over the wire. A ``PowerOn`` command, for example, would receive the
    name of the driver for that machine, look it up, get the
    :class:`HardwareControlContext`, then call `setPowerOn`.
    """

    __metaclass__ = ABCMeta

    @abstractproperty
    def name(self):
        """A stable and unique name for this driver.

        For example, "generic-impi-ia" would be suitable for a generic
        IPMI implementation for Intel Architecture machines.

        :return: A string containing only [a-zA-Z0-9-+/*].
        """

    @abstractproperty
    def description(self):
        """A description of this driver, suitable for human consumption.

        :return: A ``(one-line-desc, long-desc)`` tuple.
        """

    @abstractmethod
    def getControlContext(self):
        """Returns a :class:`HardwareControlContext` for this driver.

        For example, this might return an IPMI implementation.
        """

    @abstractmethod
    def getResourceContext(self):
        """Returns a :class:`HardwareResourceContext` for this driver.

        For example, this might return a Simple Streams implementation
        that can be shared between drivers.
        """

    @abstractmethod
    def getDiscoveryContext(self):
        """Returns a :class:`HardwareDiscoverContext` for this driver.

        For example, this might return a wrapper around a shared
        ``ipmidetectd`` daemon, or an interface to a vendor-specific
        agent.
        """


class HardwareControlContext:

    __metaclass__ = ABCMeta

    @abstractmethod
    def setPowerOn(self, machine):
        """Turn the power on.

        :param machine: Information about the machine.
        """

    @abstractmethod
    def setPowerOff(self, machine):
        """Turn the power off.

        :param machine: Information about the machine.
        """

    @abstractmethod
    def isPowerOn(self, machine):
        """True if the machine is switched on.

        :param machine: Information about the machine.
        """


class HardwareResourceContext:

    __metaclass__ = ABCMeta

    @abstractmethod
    def updateResources(self):
        """Update the resources this driver needs to operate.

        For those drivers that are in use, the region controller will
        ask them to update their own resources, perhaps by talking to a
        shared Simple Streams broker, or downloading from a vendor site.

        These resources, once obtained, need to be registered with the
        TFTP server, for example.

        TBD: How to provide progress information.
        """

    @abstractmethod
    def deleteResources(self):
        """Delete all the resources this driver has previously pulled in.

        If a driver is no longer in use, the region may choose to remove
        its resources. They would also need to be deregistered from the
        TFTP server, for example.
        """

    @abstractmethod
    def canEphemeralBoot(self, machine, system):
        """Return true if this driver has the resources to boot the machine.

        This should return false if not everything required has been
        downloaded, for example.

        :param machine: Information about the machine.

        :param system: The system to boot, e.g. Ubuntu 14.04 on AMD64.
        """

    @abstractmethod
    def canInstall(self, machine, system):
        """Return true if this driver has the resources to install the machine.

        This should return false if not everything required has been
        downloaded, for example.

        :param machine: Information about the machine.

        :param system: The system to install, e.g. Ubuntu 14.04 on AMD64.
        """


class HardwareDiscoverContext:

    __metaclass__ = ABCMeta

    @abstractmethod
    def startDiscovery(self):
        """TBD"""

    @abstractmethod
    def stopDiscovery(self):
        """TBD"""
