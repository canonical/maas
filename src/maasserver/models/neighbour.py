# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for Neighbour."""


from django.db.models import (
    CASCADE,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    Manager,
    TextField,
)
from django.db.models.query import QuerySet

from maasserver.fields import MAC_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import Interface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.network import get_mac_organization

maaslog = get_maas_logger("neighbour")


class NeighbourQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "ip": "__ip",
            "mac": "__mac_address",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs
        )


class NeighbourQuerySet(NeighbourQueriesMixin, QuerySet):
    """Custom QuerySet which mixes in some additional queries specific to
    subnets. This needs to be a mixin because an identical method is needed on
    both the Manager and all QuerySets which result from calling the manager.
    """


class NeighbourManager(Manager, NeighbourQueriesMixin):
    """A utility to manage collections of Neighbours."""

    def get_queryset(self):
        queryset = NeighbourQuerySet(self.model, using=self._db)
        return queryset

    def get_neighbour_or_404(self, specifiers):
        """Fetch a `Neighbour` by its ID or specifiers.

        :param specifiers: The neighbour specifiers.
        :type specifiers: str
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        neighbour = self.get_object_by_specifiers_or_raise(specifiers)
        return neighbour

    @staticmethod
    def get_vid_log_snippet(vid: int) -> str:
        if vid is not None:
            return " on VLAN %d" % vid
        else:
            return ""

    def delete_and_log_obsolete_neighbours(
        self, ip: str, mac: str, interface: str, vid: int
    ) -> None:
        """Removes any existing neighbours matching the specified values.

        Excludes the given MAC address from removal, since it will be updated
        rather than replaced if it exists.

        Returns True if a binding was (deleted and a log was generated).
        """
        deleted = False
        previous_bindings = self.filter(
            interface=interface, ip=ip, vid=vid
        ).exclude(mac_address=mac)
        # Technically there should be just one existing mapping for this
        # (interface, ip, vid), but the defensive thing to do is to delete
        # them all.
        for binding in previous_bindings:
            maaslog.info(
                "%s: IP address %s%s moved from %s to %s"
                % (
                    interface.get_log_string(),
                    ip,
                    self.get_vid_log_snippet(vid),
                    binding.mac_address,
                    mac,
                )
            )
            binding.delete()
            deleted = True
        return deleted

    def get_by_updated_with_related_nodes(self):
        """Returns a `QuerySet` of neighbours, while also selecting related
        interfaces and nodes.

        This method is intended to be called from the API, which will need
        data from the interface (and its related node) in order to provide
        useful, concise information about the neighbour.
        """
        return self.select_related("interface__node").order_by("-updated")


class Neighbour(CleanSave, TimestampedModel):
    """A `Neighbour` represents an (IP, MAC) pair seen from an interface.

    :ivar ip: Observed IP address.
    :ivar mac_address: IP address the MAC was observed claiming to own.
    :ivar vid: Observed 802.1Q VLAN ID.
    :ivar count: Number of times this (IP, MAC) pair was seen on the interface.
    :ivar interface: Interface the neighbour was observed on.
    :ivar objects: An instance of the class :class:`SpaceManager`.
    """

    class Meta:
        verbose_name = "Neighbour"
        verbose_name_plural = "Neighbours"
        unique_together = ("interface", "vid", "mac_address", "ip")

    # Observed IP address.
    ip = GenericIPAddressField(
        unique=False,
        null=True,
        editable=False,
        blank=True,
        default=None,
        verbose_name="IP",
    )

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
        Interface,
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=CASCADE,
    )

    # Observed MAC address.
    mac_address = TextField(null=True, blank=True, validators=[MAC_VALIDATOR])

    objects = NeighbourManager()

    @property
    def mac_organization(self):
        return get_mac_organization(str(self.mac_address))

    @property
    def observer_system_id(self):
        """Returns the system_id of the rack this neighbour was observed on."""
        return self.interface.node.system_id

    @property
    def observer_hostname(self):
        """Returns the system_id of the rack this neighbour was observed on."""
        return self.interface.node.hostname

    @property
    def observer_interface_name(self):
        """Returns the interface name this neighbour was observed on."""
        return self.interface.name

    @property
    def observer_interface(self):
        return self.interface

    @property
    def observer_interface_id(self):
        return self.interface_id
