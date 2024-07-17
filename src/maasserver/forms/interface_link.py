# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interface link form."""


from collections import Counter

from django import forms
from django.core.exceptions import ValidationError
from netaddr import IPAddress

from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_LINK_TYPE_CHOICES,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
)
from maasserver.fields import (
    CaseInsensitiveChoiceField,
    SpecifierOrModelChoiceField,
)
from maasserver.models import BondInterface, Interface, StaticIPAddress, Subnet
from maasserver.utils.forms import compose_invalid_choice_text, set_form_error
from maasserver.utils.orm import get_one

# Link modes that support the default_gateway option.
GATEWAY_OPTION_MODES = [INTERFACE_LINK_TYPE.AUTO, INTERFACE_LINK_TYPE.STATIC]


class InterfaceLinkForm(forms.Form):
    """Interface link form."""

    subnet = SpecifierOrModelChoiceField(queryset=None, required=False)

    ip_address = forms.GenericIPAddressField(required=False)

    default_gateway = forms.BooleanField(initial=False, required=False)

    def __init__(self, *args, **kwargs):
        # Get list of allowed modes for this interface.
        allowed_modes = kwargs.pop(
            "allowed_modes",
            [
                INTERFACE_LINK_TYPE.AUTO,
                INTERFACE_LINK_TYPE.DHCP,
                INTERFACE_LINK_TYPE.STATIC,
                INTERFACE_LINK_TYPE.LINK_UP,
            ],
        )
        self.force = kwargs.pop("force", False)
        mode_choices = [
            (key, value)
            for key, value in INTERFACE_LINK_TYPE_CHOICES
            if key in allowed_modes
        ]

        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)

        # Create the mode field and setup the queryset on the subnet.
        self.fields["mode"] = CaseInsensitiveChoiceField(
            choices=mode_choices,
            required=True,
            error_messages={
                "invalid_choice": compose_invalid_choice_text(
                    "mode", mode_choices
                )
            },
        )
        if self.instance.vlan is None or self.force is True:
            self.fields["subnet"].queryset = Subnet.objects.all()
        else:
            self.fields["subnet"].queryset = (
                self.instance.vlan.subnet_set.all()
            )

    def clean(self):
        for interface in self.instance.children.all():
            if isinstance(interface, BondInterface):
                set_form_error(
                    self,
                    "bond",
                    (
                        f"Cannot link interface({self.instance.name}) when "
                        f"interface is in a bond({interface.name})."
                    ),
                )
        cleaned_data = super().clean()
        mode = cleaned_data.get("mode", None)
        if mode is None:
            return cleaned_data
        elif mode == INTERFACE_LINK_TYPE.AUTO:
            self._clean_mode_auto(cleaned_data)
        elif mode == INTERFACE_LINK_TYPE.DHCP:
            self._clean_mode_dhcp()
        elif mode == INTERFACE_LINK_TYPE.STATIC:
            self._clean_mode_static(cleaned_data)
        elif mode == INTERFACE_LINK_TYPE.LINK_UP:
            self._clean_mode_link_up()
        self._clean_default_gateway(cleaned_data)
        return cleaned_data

    def _clean_mode_auto(self, cleaned_data):
        subnet = cleaned_data.get("subnet", None)
        if subnet is None:
            set_form_error(self, "subnet", "This field is required.")

    def _clean_mode_dhcp(self):
        # Can only have one DHCP link on an interface.
        dhcp_address = get_one(
            self.instance.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
        )
        if dhcp_address is not None:
            if dhcp_address.subnet is not None:
                set_form_error(
                    self,
                    "mode",
                    "Interface is already set to DHCP from '%s'."
                    % (dhcp_address.subnet),
                )
            else:
                set_form_error(
                    self, "mode", "Interface is already set to DHCP."
                )

    def _clean_mode_static(self, cleaned_data):
        subnet = cleaned_data.get("subnet", None)
        ip_address = cleaned_data.get("ip_address", None)
        if subnet is None:
            set_form_error(self, "subnet", "This field is required.")
        elif ip_address:
            ip_address = IPAddress(ip_address)
            if ip_address not in subnet.get_ipnetwork():
                set_form_error(
                    self,
                    "ip_address",
                    "IP address is not in the given subnet '%s'." % subnet,
                )
            ip_range = subnet.get_dynamic_range_for_ip(ip_address)
            if ip_range is not None:
                set_form_error(
                    self,
                    "ip_address",
                    "IP address is inside a dynamic range "
                    "%s to %s." % (ip_range.start_ip, ip_range.end_ip),
                )

    def _clean_mode_link_up(self):
        # Cannot set LINK_UP unless no other IP address are attached to
        # this interface. But exclude STICKY addresses where the IP address is
        # null, because the user could be trying to change the subnet for a
        # LINK_UP address. And exclude DISCOVERED because what MAAS discovered
        # doesn't matter with regard to the user's intention.
        exclude_types = (IPADDRESS_TYPE.STICKY, IPADDRESS_TYPE.DISCOVERED)
        has_active_links = self.instance.ip_addresses.exclude(
            alloc_type__in=exclude_types, ip__isnull=True
        ).exists()
        if has_active_links and self.force is not True:
            set_form_error(
                self,
                "mode",
                "Cannot configure interface to link up (with no IP address) "
                "while other links are already configured. Specify force=True "
                "to override this behavior and delete all links.",
            )

    def _clean_default_gateway(self, cleaned_data):
        mode = cleaned_data.get("mode", None)
        subnet = cleaned_data.get("subnet", None)
        default_gateway = cleaned_data.get("default_gateway", False)
        if not default_gateway:
            return
        if mode not in GATEWAY_OPTION_MODES:
            set_form_error(
                self, "default_gateway", "Cannot use in mode '%s'." % mode
            )
        else:
            if subnet is None:
                set_form_error(
                    self,
                    "default_gateway",
                    "Subnet is required when default_gateway is True.",
                )
            elif not subnet.gateway_ip:
                set_form_error(
                    self,
                    "default_gateway",
                    "Cannot set as default gateway because subnet "
                    "%s doesn't provide a gateway IP address." % subnet,
                )

    def save(self):
        mode = self.cleaned_data.get("mode", None)
        subnet = self.cleaned_data.get("subnet", None)
        ip_address = self.cleaned_data.get("ip_address", None)
        default_gateway = self.cleaned_data.get("default_gateway", False)
        # If force=True, allow the user to select any subnet (this will
        # implicitly change the VLAN).
        if mode == INTERFACE_LINK_TYPE.LINK_UP or self.force is True:
            # We're either setting the LINK_UP to a new subnet, or we're
            # forcing the issue.
            self.instance.clear_all_links(clearing_config=True)
        # If the user wants to force a particular subnet to be linked, clear
        # out the VLAN so that link_subnet() will reset the interface's subnet
        # to be correct.
        should_clear_vlan = (
            self.force is True
            and subnet is not None
            and self.instance.vlan is not None
        )
        if should_clear_vlan:
            self.instance.vlan = None
        if not ip_address:
            ip_address = None
        link_ip = self.instance.link_subnet(
            mode, subnet, ip_address=ip_address
        )
        if default_gateway:
            node = self.instance.get_node()
            network = subnet.get_ipnetwork()
            if network.version == IPADDRESS_FAMILY.IPv4:
                node.gateway_link_ipv4 = link_ip
            elif network.version == IPADDRESS_FAMILY.IPv6:
                node.gateway_link_ipv6 = link_ip
            else:
                raise ValueError(
                    "Unknown subnet IP version: %s" % network.version
                )
            node.save()
        return Interface.objects.get(id=self.instance.id)


class InterfaceUnlinkForm(forms.Form):
    """Interface unlink form."""

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.set_up_id_field()

    def set_up_id_field(self):
        link_ids = self.instance.ip_addresses.all().values_list(
            "id", flat=True
        )
        link_choices = [(link_id, link_id) for link_id in link_ids]
        invalid_choice = compose_invalid_choice_text("id", link_choices)
        self.fields["id"] = forms.ChoiceField(
            choices=link_choices,
            required=True,
            error_messages={"invalid_choice": invalid_choice},
        )

    def save(self):
        link_id = self.cleaned_data.get("id", None)
        self.instance.unlink_subnet_by_id(link_id)
        return Interface.objects.get(id=self.instance.id)


class InterfaceSetDefaultGatwayForm(forms.Form):
    """Interface set default gateway form."""

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super().__init__(*args, **kwargs)
        self.links = self.get_valid_links()
        self.set_up_link_id_field()

    def get_valid_links(self):
        """Return IP links on the instance that are of the correct type,
        have a subnet, and has a gateway_ip set."""
        links = self.instance.ip_addresses.filter(
            alloc_type__in=[
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.DHCP,
            ],
            subnet__isnull=False,
            subnet__gateway_ip__isnull=False,
        )
        links = links.select_related("subnet")
        return [link for link in links.all() if link.subnet.gateway_ip]

    def set_up_link_id_field(self):
        link_choices = [(link.id, link.id) for link in self.links]
        invalid_choice = compose_invalid_choice_text("link_id", link_choices)
        self.fields["link_id"] = forms.ChoiceField(
            choices=link_choices,
            required=False,
            error_messages={"invalid_choice": invalid_choice},
        )

    def _clean_has_gateways(self):
        """Sets error if the interface has not available gateways."""
        if len(self.links) == 0:
            raise ValidationError("This interface has no usable gateways.")

    def _clean_ipv4_and_ipv6_gateways(self):
        """Sets error if the interface doesn't have only one IPv4 and one
        IPv6 gateway."""
        unique_gateways = {link.subnet.gateway_ip for link in self.links}
        gateway_versions = Counter(
            IPAddress(gateway).version for gateway in unique_gateways
        )
        too_many = sorted(
            ip_family
            for ip_family, count in gateway_versions.items()
            if count > 1
        )
        if len(too_many) > 0:
            set_form_error(
                self,
                "link_id",
                "This field is required; Interface has more than "
                "one usable %s gateway%s."
                % (
                    " and ".join("IPv%d" % version for version in too_many),
                    "s" if len(too_many) > 1 else "",
                ),
            )

    def clean(self):
        self._clean_has_gateways()
        cleaned_data = super().clean()
        link_id = cleaned_data.get("link_id", None)
        if not link_id:
            self._clean_ipv4_and_ipv6_gateways()
        return cleaned_data

    def get_first_link_by_ip_family(self, ip_family):
        for link in self.links:
            if link.subnet.get_ipnetwork().version == ip_family:
                return link
        return None

    def save(self):
        link_id = self.cleaned_data.get("link_id", None)
        node = self.instance.get_node()
        if link_id:
            link = StaticIPAddress.objects.get(id=int(link_id))
            network = link.subnet.get_ipnetwork()
            if network.version == IPADDRESS_FAMILY.IPv4:
                node.gateway_link_ipv4 = link
            elif network.version == IPADDRESS_FAMILY.IPv6:
                node.gateway_link_ipv6 = link
            else:
                raise ValueError(
                    "Unknown subnet IP version: %s" % network.version
                )
            node.save()
        else:
            ipv4_link = self.get_first_link_by_ip_family(IPADDRESS_FAMILY.IPv4)
            if ipv4_link is not None:
                node.gateway_link_ipv4 = ipv4_link
            ipv6_link = self.get_first_link_by_ip_family(IPADDRESS_FAMILY.IPv6)
            if ipv6_link is not None:
                node.gateway_link_ipv6 = ipv6_link
            node.save()
        return self.instance
