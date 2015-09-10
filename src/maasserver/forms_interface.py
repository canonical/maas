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

from django import forms
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
    InterfaceRelationship,
    PhysicalInterface,
    VLANInterface,
)


class InterfaceForm(MAASModelForm):
    """Base Interface creation/edition form.

    Do not use this directly, instead, use the specialized
    versions defined below.
    """

    type = None

    parents = forms.ModelMultipleChoiceField(
        queryset=None, required=False)

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
            'vlan',
            'ipv4_params',
            'ipv6_params',
            'params',
            'tags',
            )

    def __init__(self, *args, **kwargs):
        self.node = kwargs.pop("node", None)
        super(InterfaceForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance is not None:
            self.node = instance.get_node()
            self.parents = instance.parents
        if self.node is None:
            raise ValueError(
                "instance or node is required for the InterfaceForm")
        self.fields['parents'].queryset = self.node.interface_set.all()

    def save(self, *args, **kwargs):
        """Persist the interface into the database."""
        interface = super(InterfaceForm, self).save(commit=True)
        if 'parents' in self.data:
            parents = self.cleaned_data.get('parents')
            existing_parents = set(interface.parents.all())
            if parents:
                parents = set(parents)
                for parent_to_add in parents.difference(existing_parents):
                    rel = InterfaceRelationship(
                        child=interface, parent=parent_to_add)
                    rel.save()
                for parent_to_del in existing_parents.difference(parents):
                    rel = interface.parent_relationships.filter(
                        parent=parent_to_del)
                    rel.delete()
        interface.save()
        return Interface.objects.get(id=interface.id)

    def fields_ok(self, field_list):
        """Return True if none of the fields is in error thus far."""
        return all(
            field not in self.errors for field in field_list)

    def get_clean_parents(self):
        if 'parents' in self.data or self.instance.id is None:
            parents = self.cleaned_data.get('parents')
        else:
            parents = self.instance.parents.all()
        return parents

    def clean_interface_name_uniqueness(self, name):
        node_interfaces = self.node.interface_set.filter(name=name)
        if self.instance is not None and self.instance.id is not None:
            node_interfaces = node_interfaces.exclude(
                id=self.instance.id)
        if node_interfaces.exists():
            msg = "Node %s already has an interface named '%s'." % (
                self.node, name)
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

    enabled = forms.NullBooleanField(required=False)

    class Meta:
        model = PhysicalInterface
        fields = InterfaceForm.Meta.fields + (
            'mac_address',
            'name',
            'enabled',
        )

    def __init__(self, *args, **kwargs):
        super(PhysicalInterfaceForm, self).__init__(*args, **kwargs)
        # Force MAC to be non-null.
        self.fields['mac_address'].required = True

    def _get_validation_exclusions(self):
        # The instance is created just before this in django. The only way to
        # get the validation to pass on a newly created interface is to set the
        # node in the interface here.
        self.instance.node = self.node
        return super(PhysicalInterfaceForm, self)._get_validation_exclusions()

    def clean_parents(self):
        parents = self.get_clean_parents()
        if parents is None:
            return
        if len(parents) > 0:
            msg = "A physical interface cannot have parents."
            raise ValidationError({'parents': [msg]})

    def clean(self):
        cleaned_data = super(PhysicalInterfaceForm, self).clean()
        new_name = cleaned_data.get('name')
        if self.fields_ok(['name']) and new_name:
            self.clean_interface_name_uniqueness(new_name)
        return cleaned_data


class VLANInterfaceForm(InterfaceForm):
    """Form used to create/edit a VLAN interface."""

    class Meta:
        model = VLANInterface
        fields = InterfaceForm.Meta.fields

    def clean_parents(self):
        parents = self.get_clean_parents()
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
                name = build_vlan_interface_name(
                    self.cleaned_data.get('parents').first(), new_vlan)
                self.clean_interface_name_uniqueness(name)
        return cleaned_data


class BondInterfaceForm(InterfaceForm):
    """Form used to create/edit a bond interface."""

    class Meta:
        model = BondInterface
        fields = InterfaceForm.Meta.fields + (
            'mac_address',
            'name',
        )

    def clean_parents(self):
        parents = self.get_clean_parents()
        if parents is None:
            return
        if len(parents) < 1:
            msg = "A Bond interface must have one or more parents."
            raise ValidationError({'parents': [msg]})
        return parents

    def clean(self):
        cleaned_data = super(BondInterfaceForm, self).clean()
        if self.fields_ok(['parents']):
            parents = self.cleaned_data.get('parents')
            # Set the mac_address if its missing and the interface is being
            # created.
            if parents:
                if self.instance.id is not None:
                    parent_macs = {
                        parent.mac_address.get_raw(): parent
                        for parent in self.instance.parents.all()
                    }
                mac_not_changed = (
                    self.instance.id is not None and
                    self.cleaned_data["mac_address"] == (
                        self.instance.mac_address))
                if self.instance.id is None and 'mac_address' not in self.data:
                    # New bond without mac_address set, set it to the first
                    # parent mac_address.
                    self.cleaned_data['mac_address'] = unicode(
                        parents[0].mac_address)
                elif (mac_not_changed and
                        self.instance.mac_address in parent_macs and
                        parent_macs[self.instance.mac_address] not in parents):
                    # Updating bond where its mac_address comes from its parent
                    # and that parent is no longer part of this bond. Update
                    # the mac_address to be one of the new parent MAC
                    # addresses.
                    self.cleaned_data['mac_address'] = unicode(
                        parents[0].mac_address)
        return cleaned_data


INTERFACE_FORM_MAPPING = {
    INTERFACE_TYPE.PHYSICAL: PhysicalInterfaceForm,
    INTERFACE_TYPE.VLAN: VLANInterfaceForm,
    INTERFACE_TYPE.BOND: BondInterfaceForm,
}
