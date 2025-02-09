# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VLAN form."""

from django import forms
from django.core.exceptions import ValidationError

from maasserver.enum import SERVICE_STATUS
from maasserver.fields import NodeChoiceField, SpecifierOrModelChoiceField
from maasserver.forms import MAASModelForm
from maasserver.models import Fabric, RackController, Service, Space
from maasserver.models.vlan import VLAN
from maasserver.permissions import NodePermission


class VLANForm(MAASModelForm):
    """VLAN creation/edition form."""

    # Linux doesn't allow lower than 552 for the MTU.
    mtu = forms.IntegerField(min_value=552, required=False)

    space = SpecifierOrModelChoiceField(
        queryset=Space.objects.all(), required=False, empty_label=""
    )

    fabric = SpecifierOrModelChoiceField(
        queryset=Fabric.objects.all(), required=False, empty_label=""
    )

    class Meta:
        model = VLAN
        fields = (
            "name",
            "description",
            "vid",
            "mtu",
            "dhcp_on",
            "primary_rack",
            "secondary_rack",
            "relay_vlan",
            "space",
            "fabric",
        )
        permission_create = NodePermission.admin
        permission_edit = NodePermission.admin

    def __init__(self, *args, **kwargs):
        self.fabric = kwargs.pop("fabric", None)
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance is None and self.fabric is None:
            raise ValueError("Form requires either a instance or a fabric.")
        self._set_up_rack_fields()
        self._set_up_relay_vlan()

    def _set_up_rack_fields(self):
        qs = RackController.objects.filter_by_vids([self.instance.vid])
        self.fields["primary_rack"] = NodeChoiceField(
            required=False,
            initial=None,
            empty_label="No rack controller",
            queryset=qs,
        )
        self.fields["secondary_rack"] = NodeChoiceField(
            required=False,
            initial=None,
            empty_label="No rack controller",
            queryset=qs,
        )

        # Convert the initial values pulled from the database from id to
        # system_id so form validation doesn't complain
        primary_rack_id = self.initial.get("primary_rack")
        if primary_rack_id is not None:
            primary_rack = RackController.objects.get(id=primary_rack_id)
            self.initial["primary_rack"] = primary_rack.system_id
        secondary_rack_id = self.initial.get("secondary_rack")
        if secondary_rack_id is not None:
            secondary_rack = RackController.objects.get(id=secondary_rack_id)
            self.initial["secondary_rack"] = secondary_rack.system_id

    def _set_up_relay_vlan(self):
        # Configure the relay_vlan fields to include only VLAN's that are
        # not already on a relay_vlan. If this is an update then it cannot
        # be itself or never set when dhcp_on is True.
        possible_relay_vlans = VLAN.objects.filter(relay_vlan__isnull=True)
        if self.instance is not None:
            possible_relay_vlans = possible_relay_vlans.exclude(
                id=self.instance.id
            )
            if self.instance.dhcp_on:
                possible_relay_vlans = VLAN.objects.none()
                if self.instance.relay_vlan is not None:
                    possible_relay_vlans = VLAN.objects.filter(
                        id=self.instance.relay_vlan.id
                    )
        self.fields["relay_vlan"] = forms.ModelChoiceField(
            queryset=possible_relay_vlans, required=False
        )

    def clean(self):
        cleaned_data = super().clean()
        # Automatically promote the secondary rack controller to the primary
        # if the primary is removed.
        if (
            not cleaned_data.get("primary_rack")
            and self.instance.secondary_rack is not None
        ):
            cleaned_data["primary_rack"] = self.instance.secondary_rack
            cleaned_data["secondary_rack"] = None
        # If the primary is set to the secondary remove the secondary
        if (
            cleaned_data.get("primary_rack")
            and cleaned_data["primary_rack"] == self.instance.secondary_rack
        ):
            cleaned_data["secondary_rack"] = None
        # Disallow setting the secondary to the existing primary
        if (
            cleaned_data.get("secondary_rack")
            and cleaned_data["secondary_rack"] == self.instance.primary_rack
        ):
            raise ValidationError(
                "%s is already set as the primary rack controller"
                % cleaned_data["secondary_rack"].system_id
            )
        if (
            cleaned_data.get("primary_rack")
            and cleaned_data.get("secondary_rack")
            and cleaned_data.get("primary_rack")
            == cleaned_data.get("secondary_rack")
        ):
            raise ValidationError(
                "The primary and secondary rack must be different"
            )

        # Fix LP: #1798476 - When setting the secondary rack and the primary
        # rack was originally set (and not being changed), require the primary
        # rack to be up and running.
        primary_rack = cleaned_data.get("primary_rack")
        if (
            primary_rack
            and primary_rack == self.instance.primary_rack
            and cleaned_data.get("secondary_rack")
            and cleaned_data["secondary_rack"]
            != (self.instance.secondary_rack)
        ):
            # Uses the `rackd` service not `dhcpd` or `dhcpd6` because if
            # the rackd is on it will ensure those services make it to a good
            # state.
            rackd_service = Service.objects.filter(
                node=primary_rack, name="rackd"
            ).first()
            if rackd_service and rackd_service.status == SERVICE_STATUS.DEAD:
                raise ValidationError(
                    "The primary rack controller must be up and running to "
                    "set a secondary rack controller. Without the primary "
                    "the secondary DHCP service will not be able to "
                    "synchronize, preventing it from responding to DHCP "
                    "requests."
                )

        # Only allow dhcp_on when the primary_rack is set
        if (
            cleaned_data.get("dhcp_on")
            and not self.cleaned_data.get("primary_rack")
            and not self.instance.primary_rack
        ):
            raise ValidationError(
                "dhcp can only be turned on when a primary rack controller "
                "is set."
            )
        # XXX ltrager 2016-02-09 - Hack to get around
        # https://code.djangoproject.com/ticket/25349
        # https://github.com/django/django/pull/5658
        if (
            cleaned_data.get("primary_rack") is None
            and self.instance.primary_rack is not None
        ):
            self.instance.primary_rack = None
        if (
            cleaned_data.get("secondary_rack") is None
            and self.instance.secondary_rack is not None
        ):
            self.instance.secondary_rack = None
        if cleaned_data.get("space") == "" and self.instance.space is not None:
            self.instance.space = None
        return cleaned_data

    def clean_dhcp_on(self):
        dhcp_on = self.cleaned_data.get("dhcp_on")
        if not dhcp_on:
            return dhcp_on
        for subnet in self.instance.subnet_set.all():
            if subnet.get_dynamic_ranges():
                return dhcp_on
        raise ValidationError(
            "dhcp can only be turned on when a dynamic IP range is defined."
        )

    def save(self):
        """Persist the VLAN into the database."""
        vlan = super().save(commit=False)
        if self.fabric is not None:
            vlan.fabric = self.fabric
        for key in ["space", "relay_vlan", "name"]:
            if key in self.data and not self.cleaned_data.get(key):
                # key is being cleared.
                setattr(vlan, key, None)
        if vlan.dhcp_on:
            # 'relay_vlan' cannot be set when dhcp is on.
            vlan.relay_vlan = None
        vlan.save()
        return vlan
