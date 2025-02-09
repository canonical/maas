# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for mDNS. (Multicast DNS, or RFC 6762.)"""

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    Manager,
)
from netaddr import IPAddress

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import get_one, UniqueViolation
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("mDNS")


class MDNSManager(Manager):
    """Manager for mDNS data."""

    def delete_and_log_obsolete_mdns_entries(
        self, hostname: str, ip: str, interface: str
    ) -> None:
        """Removes any existing mDNS data matching the specified values.

        Excludes the given IP address from removal, since it will be updated
        rather than replaced if it exists.

        Returns True if a binding was deleted.
        """
        # Check if this hostname was previously assigned to another IP address.
        deleted = False
        incoming_ip_version = IPAddress(ip).version
        previous_bindings = self.filter(
            hostname=hostname, interface=interface
        ).exclude(ip=ip)
        # Check if this hostname was previously assigned to a different IP.
        for binding in previous_bindings:
            if incoming_ip_version != IPAddress(binding.ip).version:
                # Don't move hostnames between address families.
                continue
            maaslog.info(
                "%s: Hostname '%s' moved from %s to %s."
                % (interface.get_log_string(), hostname, binding.ip, ip)
            )
            binding.delete()
            deleted = True
        # Check if this IP address had a different hostname assigned.
        previous_bindings = self.filter(ip=ip, interface=interface).exclude(
            hostname=hostname
        )
        for binding in previous_bindings:
            maaslog.info(
                "%s: Hostname for %s updated from '%s' to '%s'."
                % (interface.get_log_string(), ip, binding.hostname, hostname)
            )
            binding.delete()
            deleted = True
        return deleted

    def get_current_entry(self, hostname: str, ip: str, interface: str):
        """Returns the current mDNS data for the specified values.

        Returns None if an object representing the specified hostname, IP
        address, and Interface does not exist. (This is not an error condition;
        it happens normally when the binding is created for the first time.)

        The caller must ensure that any obsolete bindings are deleted before
        calling this method.
        """
        query = self.filter(interface=interface, ip=ip, hostname=hostname)
        # If we get an exception here, it is most likely due to an unlikely
        # race condition. (either that, or the caller neglected to remove
        # obsolete bindings before calling this method.) Therefore, raise
        # a UniqueViolation so this operation can be retried.
        return get_one(query, exception_class=UniqueViolation)


class MDNS(CleanSave, TimestampedModel):
    """Represents data gathered from mDNS-browse for a particular IP address.

    At the moment, the only MAAS-relevant data we are storing is the hostname.

    :ivar ip: IP address reported by mDNS-browse.
    :ivar hostanme: Hostname for the IP address reported by mDNS-browse.
    :ivar interface: Interface the mDNS data was observed on.
    :ivar objects: An instance of the class :class:`MDNSManager`.
    """

    class Meta:
        verbose_name = "mDNS binding"
        verbose_name_plural = "mDNS bindings"

    # Observed IP address.
    ip = GenericIPAddressField(
        unique=False,
        null=True,
        editable=False,
        blank=True,
        default=None,
        verbose_name="IP",
    )

    # Hostname observed from mDNS-browse.
    hostname = CharField(
        max_length=256, editable=True, null=True, blank=False, unique=False
    )

    # Rack interface the mDNS data was observed on.
    interface = ForeignKey(
        "Interface",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=CASCADE,
    )

    # The number of times this (hostname, IP) binding has been seen on the
    # interface.
    count = IntegerField(default=1)

    objects = MDNSManager()
