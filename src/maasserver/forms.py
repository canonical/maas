# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Forms."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "NodeForm",
    "MACAddressForm",
    ]

from django import forms
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
    )
from django.contrib.auth.models import User
from django.forms import ModelForm
from maasserver.fields import MACAddressFormField
from maasserver.models import (
    MACAddress,
    Node,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    )


class NodeForm(ModelForm):
    system_id = forms.CharField(
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
        required=False)
    after_commissioning_action = forms.TypedChoiceField(
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES, required=False,
        empty_value=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)

    class Meta:
        model = Node
        fields = ('hostname', 'system_id', 'after_commissioning_action')


class MACAddressForm(ModelForm):
    class Meta:
        model = MACAddress


class MACAddressForm(ModelForm):
    class Meta:
        model = MACAddress


class MultipleMACAddressField(forms.MultiValueField):
    def __init__(self, nb_macs=1, *args, **kwargs):
        fields = [MACAddressFormField() for i in xrange(nb_macs)]
        super(MultipleMACAddressField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return data_list
        return []


class NodeWithMACAddressesForm(NodeForm):

    def __init__(self, *args, **kwargs):
        super(NodeWithMACAddressesForm, self).__init__(*args, **kwargs)
        macs = [mac for mac in self.data.getlist('mac_addresses') if mac]
        self.fields['mac_addresses'] = MultipleMACAddressField(len(macs))
        self.data = self.data.copy()
        self.data['mac_addresses'] = macs

    def is_valid(self):
        valid = super(NodeWithMACAddressesForm, self).is_valid()
        # If the number of MAC Address fields is > 1, provide a unified
        # error message if the validation has failed.
        reformat_mac_address_error = (
            self.errors.get('mac_addresses', None) is not None and
            len(self.data['mac_addresses']) > 1)
        if reformat_mac_address_error:
            self.errors['mac_addresses'] = (
                ['One or more MAC Addresses is invalid.'])
        return valid

    def save(self):
        node = super(NodeWithMACAddressesForm, self).save()
        for mac in self.cleaned_data['mac_addresses']:
            node.add_mac_address(mac)
        return node


class ProfileForm(ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')


class NewUserCreationForm(UserCreationForm):
    # Add is_superuser field.
    is_superuser = forms.BooleanField(
        label="Administrator status", required=False)

    def save(self, commit=True):
        user = super(NewUserCreationForm, self).save(commit=False)
        if self.cleaned_data.get('is_superuser', False):
            user.is_superuser = True
        user.save()
        return user


class EditUserForm(UserChangeForm):
    # Override the default label.
    is_superuser = forms.BooleanField(
        label="Administrator status", required=False)

    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 'is_superuser')
