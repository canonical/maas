# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interface Forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "BondInterfaceForm",
    "InterfaceForm",
    "PhysicalInterfaceForm",
    "VLANInterfaceForm",
]

from django.core.exceptions import ValidationError
from maasserver.enum import INTERFACE_TYPE
from maasserver.forms import (
    MAASModelForm,
    set_form_error,
)
from maasserver.models.interface import (
    BondInterface,
    build_vlan_interface_name,
    Interface,
    PhysicalInterface,
    VLANInterface,
)


class InterfaceForm(MAASModelForm):
    """Base Interface creation/edition form.

    Do not use this directly, instead, use the specialized
    versions defined below.
    """

    type = None

    @staticmethod
    def get_interface_form(type):
        try:
            return INTERFACE_FORM_MAPPING[type]
        except KeyError:
            raise ValidationError({'type': [
                "Invalid interface type '%s'." % type]})

    class Meta:
        model = Interface

        fields = (
            'parents',
            'vlan',
            'ipv4_params',
            'ipv6_params',
            'params',
            )

    def save(self, *args, **kwargs):
        """Persist the interface into the database."""
        interface = super(InterfaceForm, self).save(commit=False)
        if kwargs.get('commit', True):
            interface.save(*args, **kwargs)
            self.save_m2m()  # Save many to many relations.
        return interface

    def fields_ok(self, field_list):
        """Return True if none of the fields is in error thus far."""
        return all(
            field not in self.errors for field in field_list)

    def clean_interface_name_uniqueness(self, name, node):
        node_interfaces = node.get_interfaces().filter(name=name)
        if self.instance is not None and self.instance.id is not None:
            node_interfaces = node_interfaces.exclude(
                id=self.instance.id)
        if node_interfaces.exists():
            msg = "Node %s already has an interface named '%s'." % (
                node, name)
            set_form_error(self, 'name', msg)

    def clean_parents_all_same_node(self, parents):
        if parents:
            parent_nodes = set(parent.get_node() for parent in parents)
            if len(parent_nodes) > 1:
                msg = "Parents are related to different nodes."
                set_form_error(self, 'name', msg)

    def clean(self):
        cleaned_data = super(InterfaceForm, self).clean()
        self.clean_parents_all_same_node(cleaned_data.get('parents'))
        return cleaned_data


class PhysicalInterfaceForm(InterfaceForm):
    """Form used to create/edit a physical interface."""

    class Meta:
        model = PhysicalInterface
        fields = InterfaceForm.Meta.fields + (
            'mac',
            'name',
        )

    def clean_parents(self):
        parents = self.cleaned_data.get('parents')
        if parents is None:
            return
        if len(parents) > 0:
            msg = "A physical interface cannot have parents."
            raise ValidationError({'parents': [msg]})

    def clean(self):
        cleaned_data = super(PhysicalInterfaceForm, self).clean()
        new_name = cleaned_data.get('name')
        if self.fields_ok(['name', 'mac']) and new_name:
            mac = cleaned_data.get('mac', self.instance.mac)
            self.clean_interface_name_uniqueness(new_name, mac.node)
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super(PhysicalInterfaceForm, self).__init__(*args, **kwargs)
        # Force MAC to be non-null.
        self.fields['mac'].required = True


class VLANInterfaceForm(InterfaceForm):
    """Form used to create/edit a VLAN interface."""

    class Meta:
        model = VLANInterface
        fields = InterfaceForm.Meta.fields

    def clean_parents(self):
        parents = self.cleaned_data.get('parents')
        if parents is None:
            return
        if len(parents) != 1:
            msg = "A VLAN interface must have exactly one parent."
            raise ValidationError({'parents': [msg]})
        if parents[0].type == INTERFACE_TYPE.VLAN:
            msg = (
                "A VLAN interface can't have another VLAN interface as "
                "parent.")
            raise ValidationError({'parents': [msg]})
        return parents

    def clean(self):
        cleaned_data = super(VLANInterfaceForm, self).clean()
        if self.fields_ok(['vlan', 'parents']):
            new_vlan = self.cleaned_data.get('vlan')
            if new_vlan:
                parents = self.cleaned_data.get('parents')
                name = build_vlan_interface_name(new_vlan)
                self.clean_interface_name_uniqueness(
                    name, parents[0].get_node())
        return cleaned_data


class BondInterfaceForm(InterfaceForm):
    """Form used to create/edit a bond interface."""

    class Meta:
        model = BondInterface
        fields = InterfaceForm.Meta.fields + (
            'mac',
            'name',
        )

    def clean_parents(self):
        parents = self.cleaned_data.get('parents')
        if parents is None:
            return
        if len(parents) < 2:
            msg = "A Bond interface must have two parents or more."
            raise ValidationError({'parents': [msg]})
        return parents


INTERFACE_FORM_MAPPING = {
    INTERFACE_TYPE.PHYSICAL: PhysicalInterfaceForm,
    INTERFACE_TYPE.VLAN: VLANInterfaceForm,
    INTERFACE_TYPE.BOND: BondInterfaceForm,
}
