# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Monitored service driver."""

__all__ = [
    "SERVICE_STATE",
    "Service",
    "ServiceRegistry",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
)

from provisioningserver.utils.registry import Registry


class SERVICE_STATE:
    """The vocabulary of a service expected state."""
    #: Service should be on
    ON = 'on'
    #: Service should be off
    OFF = 'off'


class Service(metaclass=ABCMeta):
    """Skeleton for a monitored service."""

    @abstractproperty
    def name(self):
        """Nice name of the service."""

    @abstractproperty
    def service_name(self):
        """Name of the service for upstart or systemd."""

    @abstractmethod
    def get_expected_state(self):
        """Return a the expected state for the service."""


class ServiceRegistry(Registry):
    """Registry for service classes."""


from provisioningserver.drivers.service.tgt import TGTService
from provisioningserver.drivers.service.dhcp import (
    DHCPv4Service,
    DHCPv6Service,
    )

builtin_services = [
    TGTService(),
    DHCPv4Service(),
    DHCPv6Service(),
    ]
for service in builtin_services:
    ServiceRegistry.register_item(service.name, service)
