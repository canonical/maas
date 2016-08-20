# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for Neighbour."""

__all__ = [
    'Neighbour',
]

from django.db.models import (
    CASCADE,
    ForeignKey,
    IntegerField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.fields import (
    MAASIPAddressField,
    MACAddressField,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import (
    get_one,
    UniqueViolation,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.network import get_mac_organization


maaslog = get_maas_logger("neighbour")


class NeighbourManager(Manager):
    """A utility to manage collections of Neighbours."""

    @staticmethod
    def get_vid_log_snippet(vid: int) -> str:
        if vid is not None:
            return " on VLAN %d" % vid
        else:
            return ""

    def delete_and_log_obsolete_neighbours(
            self, ip: str, mac: str, interface: str, vid: int) -> None:
        """Removes any existing neighbours matching the specified values.

        Excludes the given MAC address from removal, since it will be updated
        rather than replaced if it exists.

        Returns True if a binding was (deleted and a log was generated).
        """
        deleted = False
        previous_bindings = self.filter(
            interface=interface, ip=ip, vid=vid).exclude(mac_address=mac)
        # Technically there should be just one existing mapping for this
        # (interface, ip, vid), but the defensive thing to do is to delete
        # them all.
        for binding in previous_bindings:
            maaslog.info("%s: IP address %s%s moved from %s to %s" % (
                interface.get_log_string(), ip, self.get_vid_log_snippet(vid),
                binding.mac_address, mac))
            binding.delete()
            deleted = True
        return deleted

    def get_current_binding(
            self, ip: str, mac: str, interface: str, vid: int):
        """Returns the current neighbour for the specified values.

        Returns None if an object representing the specified IP, MAC,
        Interface, and VID does not exist. (This is not an error condition;
        it happens normally when the binding is created for the first time.)

        The caller must ensure that any obsolete bindings are deleted before
        calling this method.

        :raises UniqueViolation: If more than one binding is found for the
            specified interface, IP address, VID, and MAC address. (Which
            should never happen due to the `unique_together`.)
        """
        query = self.filter(
            interface=interface, ip=ip, vid=vid, mac_address=mac)
        # If we get an exception here, it is most likely due to an unlikely
        # race condition. (either that, or the caller neglected to remove
        # obsolete bindings before calling this method.) Therefore, raise
        # a UniqueViolation so this operation can be retried.
        return get_one(query, exception_class=UniqueViolation)


class Neighbour(CleanSave, TimestampedModel):
    """A `Neighbour` represents an (IP, MAC) pair seen from an interface.

    :ivar ip: Observed IP address.
    :ivar mac_address: IP address the MAC was observed claiming to own.
    :ivar vid: Observed 802.1Q VLAN ID.
    :ivar count: Number of times this (IP, MAC) pair was seen on the interface.
    :ivar interface: Interface the neighbour was observed on.
    :ivar objects: An instance of the class :class:`SpaceManager`.
    """

    class Meta(DefaultMeta):
        verbose_name = "Neighbour"
        verbose_name_plural = "Neighbours"
        unique_together = (
            ("interface", "vid", "mac_address", "ip")
        )

    # Observed IP address.
    ip = MAASIPAddressField(
        unique=False, null=True, editable=False, blank=True,
        default=None, verbose_name='IP')

    # Time the observation occurred in seconds since the epoch, as seen from
    # the rack controller.
    time = IntegerField()

    # The observed VID (802.1q VLAN ID). Note that a related VLAN interface
    # on the rack is not guaranteed to exist. Neighbours will be linked to a
    # physical, bond, or virtual bridge interface via the `interface`
    # attribute.
    vid = IntegerField(null=True, blank=True)

    # The number of times this MAC, IP mapping has been seen on the interface.
    count = IntegerField(default=1)

    # Rack interface the neighbour was observed on.
    interface = ForeignKey(
        Interface, unique=False, blank=False, null=False, editable=False,
        on_delete=CASCADE)

    # Observed MAC address.
    mac_address = MACAddressField(
        unique=False, null=True, blank=True, editable=False)

    objects = NeighbourManager()

    @property
    def mac_organization(self):
        return get_mac_organization(str(self.mac_address))
