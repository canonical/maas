# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "AdminNodeWithMACAddressesForm",
    "CommissioningForm",
    "get_action_form",
    "get_node_edit_form",
    "get_node_create_form",
    "HostnameFormField",
    "NodeForm",
    "MACAddressForm",
    "MAASAndNetworkForm",
    "NodeWithMACAddressesForm",
    "SSHKeyForm",
    "UbuntuForm",
    "AdminNodeForm",
    "NodeForm",
    ]

from django import forms
from django.contrib import messages
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm,
    )
from django.contrib.auth.models import (
    AnonymousUser,
    User,
    )
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.validators import URLValidator
from django.forms import (
    CharField,
    Form,
    ModelForm,
    )
from maasserver.config_forms import SKIP_CHECK_NAME
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    )
from maasserver.fields import MACAddressFormField
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    NodeGroup,
    SSHKey,
    )
from maasserver.node_action import compile_node_actions
from maasserver.power_parameters import POWER_TYPE_PARAMETERS
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )


def compose_invalid_choice_text(choice_of_what, valid_choices):
    """Compose an "invalid choice" string for form error messages.

    :param choice_of_what: The name for what the selected item is supposed
        to be, to be inserted into the error string.
    :type choice_of_what: basestring
    :param valid_choices: Valid choices, in Django choices format:
        (name, value).
    :type valid_choices: sequence
    """
    return "%s is not a valid %s.  It should be one of: %s." % (
        "%(value)s",
        choice_of_what,
        ", ".join(name for name, value in valid_choices),
        )


INVALID_ARCHITECTURE_MESSAGE = compose_invalid_choice_text(
    'architecture', ARCHITECTURE_CHOICES)


class NodeForm(ModelForm):
    after_commissioning_action = forms.TypedChoiceField(
        label="After commissioning",
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES, required=False,
        empty_value=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)

    architecture = forms.ChoiceField(
        choices=ARCHITECTURE_CHOICES, required=True,
        initial=ARCHITECTURE.i386,
        error_messages={'invalid_choice': INVALID_ARCHITECTURE_MESSAGE})

    class Meta:
        model = Node
        fields = (
            'hostname',
            'after_commissioning_action',
            'architecture',
            )


def remove_None_values(data):
    """Return a new dictionary without the keys corresponding to None values.
    """
    return {key: value for key, value in data.items() if value is not None}


class APIEditMixin:
    """A mixin that clears None values after the cleaning phase.

    Form data contain None values for missing fields.  This class
    removes these None values before processing the data.
    """

    def _post_clean(self):
        """Override Django's private hook _post_save to remove None values
        from 'self.cleaned_data'.

        _post_clean is where the fields of the instance get set with the data
        from self.cleaned_data.  That's why the cleanup needs to happen right
        before that.
        """
        self.cleaned_data = remove_None_values(self.cleaned_data)
        super(APIEditMixin, self)._post_clean()


class AdminNodeForm(APIEditMixin, NodeForm):
    """A version of NodeForm with adds the fields 'power_type' and
    'power_parameters'.
    """

    class Meta:
        model = Node
        fields = (
            'hostname',
            'after_commissioning_action',
            'architecture',
            'power_type',
            'power_parameters',
            )

    def __init__(self, data=None, files=None, instance=None, initial=None):
        super(AdminNodeForm, self).__init__(
            data=data, files=files, instance=instance, initial=initial)
        self.set_up_power_parameters_field(data, instance)

    def set_up_power_parameters_field(self, data, node):
        """Setup the 'power_parameter' field based on the value for the
        'power_type' field.

        We need to create the field for 'power_parameter' (which depend from
        the value of the field 'power_type') before the value for power_type
        gets validated.
        """
        if data is None:
            data = {}

        power_type = data.get('power_type', self.initial.get('power_type'))

        # If power_type is None (this is a node creation form or this
        # form deals with an API call which does not change the value of
        # 'power_type') or invalid: get the node's current 'power_type'
        # value or the default value if this form is not linked to a node.
        if power_type is None or power_type not in dict(POWER_TYPE_CHOICES):
            if node is not None:
                power_type = node.power_type
            else:
                power_type = POWER_TYPE.DEFAULT
        self.fields['power_parameters'] = (
            POWER_TYPE_PARAMETERS[power_type])

    def clean(self):
        cleaned_data = super(AdminNodeForm, self).clean()
        # If power_type is DEFAULT and power_parameters_skip_check is not
        # on, reset power_parameters (set it to the empty string).
        is_default = cleaned_data['power_type'] == POWER_TYPE.DEFAULT
        skip_check = (
            self.data.get('power_parameters_%s' % SKIP_CHECK_NAME) == 'true')
        if is_default and not skip_check:
            cleaned_data['power_parameters'] = ''
        return cleaned_data


def get_node_edit_form(user):
    if user.is_superuser:
        return AdminNodeForm
    else:
        return NodeForm


class MACAddressForm(ModelForm):
    class Meta:
        model = MACAddress

    def __init__(self, node, *args, **kwargs):
        super(MACAddressForm, self).__init__(*args, **kwargs)
        self.node = node

    def save(self, *args, **kwargs):
        mac = super(MACAddressForm, self).save(commit=False)
        mac.node = self.node
        if kwargs.get('commit', True):
            mac.save(*args, **kwargs)
        return mac


class SSHKeyForm(ModelForm):
    key = forms.CharField(
        label="Public key",
        widget=forms.Textarea(attrs={'rows': '5', 'cols': '30'}),
        required=True)

    class Meta:
        model = SSHKey

    def __init__(self, user, *args, **kwargs):
        super(SSHKeyForm, self).__init__(*args, **kwargs)
        self.user = user

    def validate_unique(self):
        # This is a trick to work around a problem in Django.
        # See https://code.djangoproject.com/ticket/13091#comment:19 for
        # details.
        # Without this overridden validate_unique the validation error that
        # can occur if this user already has the same key registered would
        # occur when save() would be called.  The error would be an
        # IntegrityError raised when inserting the new key in the database
        # rather than a proper ValidationError raised by 'clean'.

        # Set the instance user.
        self.instance.user = self.user

        # Allow checking against the missing attribute.
        exclude = self._get_validation_exclusions()
        exclude.remove('user')
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError, e:
            # Publish this error as a 'key' error rather than a 'general'
            # error because only the 'key' errors are displayed on the
            # 'add key' form.
            error = e.message_dict.pop('__all__')
            e.message_dict['key'] = error
            self._update_errors(e.message_dict)


class MultipleMACAddressField(forms.MultiValueField):

    def __init__(self, nb_macs=1, *args, **kwargs):
        fields = [MACAddressFormField() for i in range(nb_macs)]
        super(MultipleMACAddressField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return data_list
        return []


def initialize_node_group(node):
    """If `node` is not in a node group yet, enroll it in the master group."""
    if node.nodegroup is None:
        node.nodegroup = NodeGroup.objects.ensure_master()


class WithMACAddressesMixin:
    """A form mixin which dynamically adds a MultipleMACAddressField to the
    list of fields.  This mixin also overrides the 'save' method to persist
    the list of MAC addresses and is intended to be used with a class
    inheriting from NodeForm.
    """

    def __init__(self, *args, **kwargs):
        super(WithMACAddressesMixin, self).__init__(*args, **kwargs)
        self.set_up_mac_addresses_field()

    def set_up_mac_addresses_field(self):
        macs = [mac for mac in self.data.getlist('mac_addresses') if mac]
        self.fields['mac_addresses'] = MultipleMACAddressField(len(macs))
        self.data = self.data.copy()
        self.data['mac_addresses'] = macs

    def is_valid(self):
        valid = super(WithMACAddressesMixin, self).is_valid()
        # If the number of MAC address fields is > 1, provide a unified
        # error message if the validation has failed.
        reformat_mac_address_error = (
            self.errors.get('mac_addresses', None) is not None and
            len(self.data['mac_addresses']) > 1)
        if reformat_mac_address_error:
            self.errors['mac_addresses'] = (
                ['One or more MAC addresses is invalid.'])
        return valid

    def clean_mac_addresses(self):
        data = self.cleaned_data['mac_addresses']
        for mac in data:
            if MACAddress.objects.filter(mac_address=mac.lower()).count() > 0:
                raise ValidationError(
                    {'mac_addresses': [
                        'Mac address %s already in use.' % mac]})
        return data

    def save(self):
        """Save the form's data to the database.

        This implementation of `save` does not support the `commit` argument.
        """
        node = super(WithMACAddressesMixin, self).save(commit=False)
        # We have to save this node in order to attach MACAddress
        # records to it.  But its nodegroup must be initialized before
        # we can do that.
        initialize_node_group(node)
        node.save()
        for mac in self.cleaned_data['mac_addresses']:
            node.add_mac_address(mac)
        if self.cleaned_data['hostname'] == "":
            node.set_mac_based_hostname(self.cleaned_data['mac_addresses'][0])
        return node


class AdminNodeWithMACAddressesForm(WithMACAddressesMixin, AdminNodeForm):
    """A version of the AdminNodeForm which includes the multi-MAC address
    field.
    """


class NodeWithMACAddressesForm(WithMACAddressesMixin, NodeForm):
    """A version of the NodeForm which includes the multi-MAC address field.
    """


def get_node_create_form(user):
    if user.is_superuser:
        return AdminNodeWithMACAddressesForm
    else:
        return NodeWithMACAddressesForm


class NodeActionForm(forms.Form):
    """Base form for performing a node action.

    This form class should not be used directly but through subclasses
    created using `get_action_form`.
    """

    user = AnonymousUser()
    request = None

    # The name of the input button used with this form.
    input_name = 'node_action'

    def __init__(self, instance, *args, **kwargs):
        super(NodeActionForm, self).__init__(*args, **kwargs)
        self.node = instance
        self.actions = compile_node_actions(instance, self.user, self.request)
        self.action_buttons = self.actions.values()

    def display_message(self, message):
        """Show `message` as feedback after performing an action."""
        if self.request is not None:
            messages.add_message(self.request, messages.INFO, message)

    def save(self):
        """An action was requested.  Perform it.

        This implementation of `save` does not support the `commit` argument.
        """
        action_name = self.data.get(self.input_name)
        action = self.actions.get(action_name)
        if action is None or not action.is_permitted():
            raise PermissionDenied("Not a permitted action: %s" % action_name)
        if action.inhibition is not None:
            raise PermissionDenied(action.inhibition)
        message = action.execute()
        self.display_message(message)


def get_action_form(user, request=None):
    """Return a class derived from NodeActionForm for a specific user.

    :param user: The user for which to build a form derived from
        NodeActionForm.
    :type user: :class:`django.contrib.auth.models.User`
    :param request: An optional request object to publish action messages.
    :type request: django.http.HttpRequest
    :return: A form class derived from NodeActionForm.
    :rtype: class:`django.forms.Form`
    """
    return type(
        str("SpecificNodeActionForm"), (NodeActionForm,),
        {'user': user, 'request': request})


class ProfileForm(ModelForm):
    # We use the field 'last_name' to store the user's full name (and
    # don't display Django's 'first_name' field).
    last_name = forms.CharField(
        label="Full name", max_length=30, required=False)

    class Meta:
        model = User
        fields = ('last_name', 'email')


class NewUserCreationForm(UserCreationForm):
    is_superuser = forms.BooleanField(
        label="MAAS administrator", required=False)

    def __init__(self, *args, **kwargs):
        super(NewUserCreationForm, self).__init__(*args, **kwargs)
        # Insert 'last_name' field at the right place (right after
        # the 'username' field).
        self.fields.insert(
            1, 'last_name',
            forms.CharField(label="Full name", max_length=30, required=False))
        # Insert 'email' field at the right place (right after
        # the 'last_name' field).
        self.fields.insert(
            2, 'email',
            forms.EmailField(
                label="E-mail address", max_length=75, required=False))

    def save(self, commit=True):
        user = super(NewUserCreationForm, self).save(commit=False)
        if self.cleaned_data.get('is_superuser', False):
            user.is_superuser = True
        new_last_name = self.cleaned_data.get('last_name', None)
        if new_last_name is not None:
            user.last_name = new_last_name
        new_email = self.cleaned_data.get('email', None)
        if new_email is not None:
            user.email = new_email
        if commit:
            user.save()
        return user

    def clean_email(self):
        """Validate that the supplied email address is unique for the
        site.
        """
        email = self.cleaned_data['email']
        email_count = User.objects.filter(email__iexact=email).count()
        if email_count != 0:
            raise forms.ValidationError(
                "User with this E-mail address already exists.")
        return email


class EditUserForm(UserChangeForm):
    # Override the default label.
    is_superuser = forms.BooleanField(
        label="MAAS administrator", required=False)
    last_name = forms.CharField(
        label="Full name", max_length=30, required=False)

    class Meta:
        model = User
        fields = (
            'username', 'last_name', 'email', 'is_superuser')

    def __init__(self, *args, **kwargs):
        super(EditUserForm, self).__init__(*args, **kwargs)
        # Django 1.4 overrides the field 'password' thus adding it
        # post-facto to the list of the selected fields (Meta.fields).
        # Here we don't want to use this form to edit the password.
        if 'password' in self.fields:
            del self.fields['password']


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

        This implementation of `save` does not support the `commit` argument.

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


class MAASAndNetworkForm(ConfigForm):
    """Settings page, MAAS and Network section."""
    maas_name = forms.CharField(label="MAAS name")
    enlistment_domain = forms.CharField(
        label="Default domain for new nodes", required=False, help_text=(
            "If 'local' is chosen, nodes must be using mDNS. Leave empty to "
            "use hostnames without a domain for newly enlisted nodes."))
    enable_dns = forms.BooleanField(
        label="Enable DNS", required=False, help_text=(
            "When enabled, MAAS will use the machine's BIND server to "
            "publish its DNS zones."
        ))


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
        """Save the archive name in the Config table.

        This implementation of `save` does not support the `commit` argument.
        """
        archive_name = self.cleaned_data.get('archive_name')
        archives = Config.objects.get_config('update_from_choice')
        archives.append([archive_name, archive_name])
        Config.objects.set_config('update_from_choice', archives)
