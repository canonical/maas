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
    "CommissioningForm",
    "get_action_form",
    "HostnameFormField",
    "NodeForm",
    "MACAddressForm",
    "MAASAndNetworkForm",
    "NodeActionForm",
    "SSHKeyForm",
    "UbuntuForm",
    "UIAdminNodeEditForm",
    "UINodeEditForm",
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
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    NODE_PERMISSION,
    NODE_STATUS,
    )
from maasserver.fields import MACAddressFormField
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    SSHKey,
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
    system_id = forms.CharField(
        widget=forms.TextInput(attrs={'readonly': 'readonly'}),
        required=False)

    # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.

    #after_commissioning_action = forms.TypedChoiceField(
    #    label="After commissioning",
    #    choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES, required=False,
    #    empty_value=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)

    architecture = forms.ChoiceField(
        choices=ARCHITECTURE_CHOICES, required=True,
        initial=ARCHITECTURE.i386,
        error_messages={'invalid_choice': INVALID_ARCHITECTURE_MESSAGE})

    class Meta:
        model = Node
        fields = (
            'hostname',
            'system_id',
            # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.
            #'after_commissioning_action',
            'architecture',
            'power_type',
            )


class UINodeEditForm(ModelForm):

    # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.

    #after_commissioning_action = forms.ChoiceField(
    #    label="After commissioning",
    #    choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES)

    class Meta:
        model = Node
        fields = (
            'hostname',
            # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.
            #'after_commissioning_action',
            )


class UIAdminNodeEditForm(ModelForm):

    # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.

    #after_commissioning_action = forms.ChoiceField(
    #    label="After commissioning",
    #    choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES)

    class Meta:
        model = Node
        fields = (
            'hostname',
            # XXX JeroenVermeulen 2012-04-12, bug=979539: re-enable.
            #'after_commissioning_action',
            'power_type',
            )


class MACAddressForm(ModelForm):
    class Meta:
        model = MACAddress


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

    def clean_mac_addresses(self):
        data = self.cleaned_data['mac_addresses']
        for mac in data:
            if MACAddress.objects.filter(mac_address=mac.lower()).count() > 0:
                raise ValidationError(
                    {'mac_addresses': [
                        'Mac address %s already in use.' % mac]})
        return data

    def save(self):
        node = super(NodeWithMACAddressesForm, self).save()
        for mac in self.cleaned_data['mac_addresses']:
            node.add_mac_address(mac)
        if self.cleaned_data['hostname'] == "":
            node.set_mac_based_hostname(self.cleaned_data['mac_addresses'][0])
        return node


def start_node(node, user):
    """Start a node from the UI.  It will have no meta_data."""
    Node.objects.start_nodes([node.system_id], user)


# Node actions per status.
#
# This maps each NODE_STATUS to a list of actions applicable to a node
# in that state:
#
# {
#     NODE_STATUS.<statusX>: [action1, action2],
#     NODE_STATUS.<statusY>: [action1],
#     NODE_STATUS.<statusZ>: [action1, action2, action3],
# }
#
# The available actions (insofar as the user has privileges to use them)
# show up in the user interface as buttons on the node page.
#
# Each action is a dict:
#
# {
#     # Action's display name; will be shown in the button.
#     'display': "Paint node",
#     # Permission required to perform action.
#     'permission': NODE_PERMISSION.EDIT,
#     # Callable that performs action.  Takes parameters (node, user).
#     'execute': lambda node, user: paint_node(
#                    node, favourite_colour(user)),
# }
#
NODE_ACTIONS = {
    NODE_STATUS.DECLARED: [
        {
            'display': "Accept & commission",
            'permission': NODE_PERMISSION.ADMIN,
            'execute': lambda node, user: Node.start_commissioning(node, user),
            'message': "Node commissioning started."
        },
    ],
    NODE_STATUS.READY: [
        {
            'display': "Start node",
            'permission': NODE_PERMISSION.EDIT,
            'execute': start_node,
            'message': "Node started."
        },
    ],
    NODE_STATUS.ALLOCATED: [
        {
            'display': "Start node",
            'permission': NODE_PERMISSION.EDIT,
            'execute': start_node,
            'message': "Node started."
        },
    ],
}


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
        self.action_buttons = self.available_action_methods(
            self.node, self.user)
        # Create a convenient dict to fetch the action's name and
        # the permission to be checked from the button name.
        self.action_dict = {
            action['display']: (
                action['permission'], action['execute'], action['message'])
            for action in self.action_buttons
        }

    def available_action_methods(self, node, user):
        """Return the actions that this user is allowed to perform on a node.

        :param node: The node for which the check should be performed.
        :type node: :class:`maasserver.models.Node`
        :param user: The user who would be performing the action.  Only the
            actions available to this user will be returned.
        :type user: :class:`django.contrib.auth.models.User`
        :return: Any applicable action dicts, as found in NODE_ACTIONS.
        :rtype: Sequence
        """
        return [
            action for action in NODE_ACTIONS.get(node.status, ())
            if user.has_perm(action['permission'], node)]

    def display_message(self, message):
        if self.request is not None:
            messages.add_message(self.request, messages.INFO, message)

    def save(self):
        action_name = self.data.get(self.input_name)
        permission, execute, message = (
            self.action_dict.get(action_name, (None, None, None)))
        if execute is not None:
            if not self.user.has_perm(permission, self.node):
                raise PermissionDenied()
            execute(self.node, self.user)
            self.display_message(message)
        else:
            raise PermissionDenied()


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


class MAASAndNetworkForm(ConfigForm):
    """Settings page, MAAS and Network section."""
    maas_name = forms.CharField(label="MAAS name")
    enlistment_domain = forms.CharField(
        label="Default domain for new nodes", required=False, help_text=(
            "If 'local' is chosen, nodes must be using mDNS. Leave empty to "
            "use hostnames without a domain for newly enlisted nodes."))


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
