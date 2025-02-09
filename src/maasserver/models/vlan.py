# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VLAN objects."""

from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    Count,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    Manager,
    PROTECT,
    Q,
    SET_NULL,
    TextField,
)
from django.db.models.query import QuerySet
from netaddr import AddrFormatError

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import NODE_TYPE
from maasserver.fields import MODEL_NAME_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.interface import VLANInterface
from maasserver.models.notification import Notification
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin, post_commit_do
from maasserver.workflow import start_workflow
from provisioningserver.utils.network import parse_integer

DEFAULT_VLAN_NAME = "Default VLAN"
DEFAULT_VID = 0
DEFAULT_MTU = 1500


def validate_vid(vid):
    """Raises a ValidationError if the given VID is not valid."""
    if vid < 0 or vid >= 0xFFF:
        raise ValidationError(
            "VLAN tag (VID) out of range (0-4094; 0 for untagged.)"
        )


class VLANQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # Circular imports.
        from maasserver.models import Fabric, Space, Subnet

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "fabric": (Fabric.objects, "vlan"),
            "id": "__id",
            "name": "__name",
            "subnet": (Subnet.objects, "vlan"),
            "space": (Space.objects, "vlan"),
            "vid": self._add_vid_query,
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )

    def _add_default_query(self, current_q, op, item):
        """If the item we're matching is an integer, first try to locate the
        object by its ID. Otherwise, search by name.
        """
        try:
            # Check if the user passed in a VID.
            vid = parse_integer(item)
        except ValueError:
            vid = None
            pass
        if item == "untagged":
            vid = 0

        if vid is not None:
            # We could do something like this here, if you actually need to
            # look up the VLAN by its ID:
            # if isinstance(item, unicode) and item.strip().startswith('vlan-')
            # ... but it's better to use VID, since that means something to
            # the user (and you always need to qualify a VLAN with its fabric
            # anyway).
            validate_vid(vid)
            return op(current_q, Q(vid=vid))
        else:
            return op(current_q, Q(name=item))

    def _add_vid_query(self, current_q, op, item):
        if item.lower() == "untagged":
            vid = 0
        else:
            vid = parse_integer(item)
        validate_vid(vid)
        current_q = op(current_q, Q(vid=vid))
        return current_q

    def validate_filter_specifiers(self, specifiers):
        """Validate the given filter string."""
        try:
            self.filter_by_specifiers(specifiers)
        except (ValueError, AddrFormatError) as e:
            raise ValidationError(e.message)  # noqa: B904


class VLANQuerySet(QuerySet, VLANQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class VLANManager(Manager, VLANQueriesMixin):
    """Manager for :class:`VLAN` model."""

    def get_queryset(self):
        queryset = VLANQuerySet(self.model, using=self._db)
        return queryset

    def get_default_vlan(self):
        """Return the default VLAN of the default fabric."""
        # Circular imports
        from maasserver.models.fabric import Fabric

        return Fabric.objects.get_default_fabric().get_default_vlan()


class VLAN(CleanSave, TimestampedModel):
    """A `VLAN`.

    :ivar name: The short-human-identifiable name for this VLAN.
    :ivar vid: The VLAN ID of this VLAN.
    :ivar fabric: The `Fabric` this VLAN belongs to.
    """

    objects = VLANManager()

    class Meta:
        verbose_name = "VLAN"
        verbose_name_plural = "VLANs"
        unique_together = (("vid", "fabric"),)

    name = CharField(
        max_length=256,
        editable=True,
        null=True,
        blank=True,
        validators=[MODEL_NAME_VALIDATOR],
    )

    description = TextField(null=False, blank=True)

    vid = IntegerField(editable=True)

    fabric = ForeignKey(
        "Fabric", blank=False, editable=True, on_delete=CASCADE
    )

    mtu = IntegerField(default=DEFAULT_MTU)

    dhcp_on = BooleanField(default=False, editable=True)

    external_dhcp = GenericIPAddressField(
        null=True, editable=False, blank=True, default=None
    )

    primary_rack = ForeignKey(
        "RackController",
        null=True,
        blank=True,
        editable=True,
        related_name="+",
        on_delete=PROTECT,
    )

    secondary_rack = ForeignKey(
        "RackController",
        null=True,
        blank=True,
        editable=True,
        related_name="+",
        on_delete=PROTECT,
    )

    relay_vlan = ForeignKey(
        "self",
        null=True,
        blank=True,
        editable=True,
        related_name="relay_vlans",
        on_delete=SET_NULL,
    )

    space = ForeignKey(
        "Space", editable=True, blank=True, null=True, on_delete=SET_NULL
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_dhcp_on = None
        self._previous_relay_vlan_id = None
        self._previous_mtu = None
        self._previous_primary_rack_id = None
        self._previous_secondary_rack_id = None
        self._updated = False

    def __setattr__(self, name, value):
        if (
            hasattr(self, f"_previous_{name}")
            and getattr(self, f"_previous_{name}") is None
        ):
            setattr(self, f"_previous_{name}", getattr(self, name))
            self._updated = True
        super().__setattr__(name, value)

    def __str__(self):
        return f"{self.fabric.get_name()}.{self.get_name()}"

    def clean_vid(self):
        if self.vid is None or self.vid < 0 or self.vid > 4094:
            raise ValidationError({"vid": ["VID must be between 0 and 4094."]})

    def clean_mtu(self):
        # Linux doesn't allow lower than 552 for the MTU.
        if self.mtu < 552 or self.mtu > 65535:
            raise ValidationError(
                {"mtu": ["MTU must be between 552 and 65535."]}
            )

    def clean(self):
        self.clean_vid()
        self.clean_mtu()

    def is_fabric_default(self):
        """Is this the default VLAN in the fabric?"""
        return self.fabric.get_default_vlan() == self

    def get_name(self):
        """Return the name of the VLAN if set; otherwise, return `None`."""
        if self.is_fabric_default():
            return "untagged"
        else:
            return self.name

    def manage_connected_interfaces(self):
        """Deal with connected interfaces:

        - delete all VLAN interfaces.
        - reconnect the other interfaces to the default VLAN of the fabric.
        """
        for interface in self.interface_set.all():
            if isinstance(interface, VLANInterface):
                interface.delete()
            else:
                interface.vlan = self.fabric.get_default_vlan()
                interface.save()

    def manage_connected_subnets(self):
        """Reconnect subnets the default VLAN of the fabric."""
        for subnet in self.subnet_set.all():
            subnet.vlan = self.fabric.get_default_vlan()
            subnet.save()

    def unique_error_message(self, model_class, unique_check):
        if set(unique_check) == {"vid", "fabric"}:
            return (
                "A VLAN with the specified VID already exists in the "
                "destination fabric."
            )
        else:
            return super().unique_error_message(model_class, unique_check)

    def _needs_dhcp_update(self):
        return self._updated and (
            self._previous_dhcp_on != self.dhcp_on
            or self._previous_relay_vlan_id != self.relay_vlan_id
            or (
                (self.dhcp_on or self.relay_vlan_id)
                and (
                    self._previous_mtu != self.mtu
                    or self._previous_primary_rack_id != self.primary_rack_id
                    or self._previous_secondary_rack_id
                    != self.secondary_rack_id
                )
            )
        )

    def delete(self):
        if self.is_fabric_default():
            raise ValidationError(
                "This VLAN is the default VLAN in the fabric, "
                "it cannot be deleted."
            )
        self.manage_connected_interfaces()
        self.manage_connected_subnets()

        needs_dhcp_update = self.dhcp_on or self.relay_vlan_id
        rack_controller_system_ids = []

        if needs_dhcp_update:
            if self.primary_rack:
                rack_controller_system_ids.append(self.primary_rack.system_id)
            if self.secondary_rack:
                rack_controller_system_ids.append(
                    self.secondary_rack.system_id
                )

        super().delete()

        if needs_dhcp_update:
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(
                    system_ids=rack_controller_system_ids
                ),
                task_queue="region",
            )

    def save(self, *args, **kwargs):
        # Bug 1555759: Raise a Notification if there are no VLANs with DHCP
        # enabled.  Clear it when one gets enabled.
        notifications = Notification.objects.filter(
            ident="dhcp_disabled_all_vlans"
        )
        if self.dhcp_on:
            # No longer true.  Delete the notification.
            notifications.delete()
        elif (
            not notifications.exists()
            and not VLAN.objects.filter(dhcp_on=True).exists()
        ):
            Notification.objects.create_warning_for_admins(
                "DHCP is not enabled on any VLAN.  This will prevent "
                "machines from being able to PXE boot, unless an external "
                "DHCP server is being used.",
                ident="dhcp_disabled_all_vlans",
            )

        created = self.id is None
        super().save(*args, **kwargs)
        # Circular dependencies.
        from maasserver.models import Fabric

        # Delete any now-empty fabrics.
        fabrics_with_vlan_count = Fabric.objects.annotate(
            vlan_count=Count("vlan")
        )
        fabrics_with_vlan_count.filter(vlan_count=0).delete()

        if created and not (self.dhcp_on or self.relay_vlan_id):
            return

        elif created or self._needs_dhcp_update():
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(vlan_ids=[self.id]),
                task_queue="region",
            )

    def connected_rack_controllers(self, exclude_racks=None):
        """Return list of rack controllers that are connected to this VLAN.

        :param exclude_racks: Exclude these rack controllers from the returned
            connected list.
        :returns: Returns a list of rack controllers that have a connection
            to this VLAN.
        """
        query = self.interface_set.filter(
            node_config__node__node_type__in=[
                NODE_TYPE.RACK_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            ]
        )
        if exclude_racks is not None:
            query = query.exclude(node_config__node__in=exclude_racks)
        return [nic.node_config.node.as_rack_controller() for nic in query]
