# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Forms."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "CommissioningForm",
    "HostnameFormField",
    "NodeForm",
    "MACAddressForm",
    "MaaSAndNetworkForm",
    "UbuntuForm",
    ]

from django import forms
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
    )
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.forms import (
    CharField,
    Form,
    ModelForm,
    )
from maasserver.fields import MACAddressFormField
from maasserver.models import (
    ARCHITECTURE_CHOICES,
    Config,
    MACAddress,
    Node,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    )


INVALID_ARCHITECTURE_MESSAGE = (
    "%(value)s is not a valid architecture. " +
    "It should be one of: %s." % ", ".join(
        name for name, value in ARCHITECTURE_CHOICES))


class NodeForm(ModelForm):
    system_id = forms.CharField(
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
        required=False)
    after_commissioning_action = forms.TypedChoiceField(
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES, required=False,
        empty_value=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)
    architecture = forms.ChoiceField(
        choices=ARCHITECTURE_CHOICES, required=False,
        error_messages={'invalid_choice': INVALID_ARCHITECTURE_MESSAGE})

    class Meta:
        model = Node
        fields = (
            'hostname', 'system_id', 'after_commissioning_action',
            'architecture')


class MACAddressForm(ModelForm):
    class Meta:
        model = MACAddress


class MultipleMACAddressField(forms.MultiValueField):
    def __init__(self, nb_macs=1, *args, **kwargs):
        fields = [MACAddressFormField() for i in range(nb_macs)]
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
    # We use the field 'last_name' to store the user's full name (and
    # don't display Django's 'first_name' field).
    last_name = forms.CharField(
        label="Full name", max_length=30, required=False)

    class Meta:
        model = User
        fields = ('last_name', 'email')


class NewUserCreationForm(UserCreationForm):
    # Add is_superuser field.
    is_superuser = forms.BooleanField(
        label="MaaS administrator", required=False)

    def __init__(self, *args, **kwargs):
        super(NewUserCreationForm, self).__init__(*args, **kwargs)
        # Insert 'last_name' field at the right place (right after
        # the 'username' field).
        self.fields.insert(
            1, 'last_name',
            forms.CharField(label="Full name", max_length=30, required=False))

    def save(self, commit=True):
        user = super(NewUserCreationForm, self).save(commit=False)
        if self.cleaned_data.get('is_superuser', False):
            user.is_superuser = True
        new_last_name = self.cleaned_data.get('last_name', None)
        if new_last_name is not None:
            user.last_name = new_last_name
        user.save()
        return user


class EditUserForm(UserChangeForm):
    # Override the default label.
    is_superuser = forms.BooleanField(
        label="MaaS administrator", required=False)
    last_name = forms.CharField(
        label="Full name", max_length=30, required=False)

    class Meta:
        model = User
        fields = (
            'username', 'last_name', 'email', 'is_superuser')


class ConfigForm(Form):
    """A base class for forms that save the content of their fields into
    Config objects.
    """

    def __init__(self, *args, **kwargs):
        super(ConfigForm, self).__init__(*args, **kwargs)
        if 'initial' not in kwargs:
            self._load_initials()

    def _load_initials(self):
        self.initial = {}
        for name in self.fields.keys():
            conf = Config.objects.get_config(name)
            if conf is not None:
                self.initial[name] = conf

    def save(self):
        """Save the content of the fields into the database.

        :return: Whether or not the content of the fields was valid and hence
            sucessfully saved into the detabase.
        :rtype: boolean
        """
        self.full_clean()
        if self._errors:
            return False
        else:
            for name, value in self.cleaned_data.items():
                Config.objects.set_config(name, value)
            return True


class MaaSAndNetworkForm(ConfigForm):
    """Settings page, MaaS and Network section."""
    maas_name = forms.CharField(label="MaaS name")
    provide_dhcp = forms.BooleanField(
        label="Provide DHCP on this subnet", required=False)


class CommissioningForm(ConfigForm):
    """Settings page, CommissioningF section."""
    check_compatibility = forms.BooleanField(
        label="Check component compatibility and certification",
        required=False)
    after_commissioning = forms.ChoiceField(
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
        label="After commissioning")


class UbuntuForm(ConfigForm):
    """Settings page, Ubuntu section."""
    fallback_master_archive = forms.BooleanField(
        label="Fallback to Ubuntu master archive",
        required=False)
    keep_mirror_list_uptodate = forms.BooleanField(
        label="Keep mirror list up to date",
        required=False)
    fetch_new_releases = forms.BooleanField(
        label="Fetch new releases automatically",
        required=False)

    def __init__(self, *args, **kwargs):
        super(UbuntuForm, self).__init__(*args, **kwargs)
        # The field 'update_from' must be added dynamically because its
        # 'choices' must be evaluated each time the form is instantiated.
        self.fields['update_from'] = forms.ChoiceField(
            label="Update from",
            choices=Config.objects.get_config('update_from_choice'))
        # The list of fields has changed: load initial values.
        self._load_initials()


hostname_error_msg = "Enter a valid hostname (e.g. host.example.com)."


def validate_hostname(value):
    try:
        validator = URLValidator(verify_exists=False)
        validator('http://%s' % value)
    except ValidationError:
        raise ValidationError(hostname_error_msg)


class HostnameFormField(CharField):

    def __init__(self, *args, **kwargs):
        super(HostnameFormField, self).__init__(
            validators=[validate_hostname], *args, **kwargs)


class AddArchiveForm(ConfigForm):
    archive_name = HostnameFormField(label="Archive name")

    def save(self):
        """Save the archive name in the Config table."""
        archive_name = self.cleaned_data.get('archive_name')
        archives = Config.objects.get_config('update_from_choice')
        archives.append([archive_name, archive_name])
        Config.objects.set_config('update_from_choice', archives)
