# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "AdminNodeForm",
    "AdminNodeWithMACAddressesForm",
    "BulkNodeActionForm",
    "CommissioningForm",
    "CommissioningScriptForm",
    "DownloadProgressForm",
    "get_action_form",
    "get_node_edit_form",
    "get_node_create_form",
    "list_all_usable_architectures",
    "MAASAndNetworkForm",
    "MACAddressForm",
    "NetworkConnectMACsForm",
    "NetworkDisconnectMACsForm",
    "NetworkForm",
    "NetworksListingForm",
    "NodeGroupEdit",
    "NodeGroupInterfaceForeignDHCPForm",
    "NodeGroupInterfaceForm",
    "NodeGroupWithInterfacesForm",
    "NodeWithMACAddressesForm",
    "SSHKeyForm",
    "TagForm",
    "ThirdPartyDriversForm",
    "UbuntuForm",
    "ZoneForm",
    ]

import collections
import json
import pipes
import re

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
from django.core.exceptions import ValidationError
from django.forms import (
    Form,
    MultipleChoiceField,
    )
from django.utils.safestring import mark_safe
from lxml import etree
from maasserver.api_utils import get_overridden_query_dict
from maasserver.clusterrpc.power_parameters import (
    get_power_type_choices,
    get_power_type_parameters,
    get_power_types,
    )
from maasserver.config_forms import SKIP_CHECK_NAME
from maasserver.enum import (
    COMMISSIONING_DISTRO_SERIES_CHOICES,
    DISTRO_SERIES,
    DISTRO_SERIES_CHOICES,
    NODE_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
    )
from maasserver.exceptions import ClusterUnavailable
from maasserver.fields import (
    MACAddressFormField,
    NodeGroupFormField,
    )
from maasserver.forms_settings import (
    CONFIG_ITEMS_KEYS,
    get_config_field,
    INVALID_DISTRO_SERIES_MESSAGE,
    INVALID_SETTING_MSG_TEMPLATE,
    )
from maasserver.models import (
    BootImage,
    Config,
    DownloadProgress,
    MACAddress,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    Tag,
    Zone,
    )
from maasserver.models.nodegroup import NODEGROUP_CLUSTER_NAME_TEMPLATE
from maasserver.node_action import (
    ACTION_CLASSES,
    ACTIONS_DICT,
    compile_node_actions,
    )
from maasserver.utils import strip_domain
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.network import make_network
from metadataserver.fields import Bin
from metadataserver.models import CommissioningScript

# A reusable null-option for choice fields.
BLANK_CHOICE = ('', '-------')


def remove_None_values(data):
    """Return a new dictionary without the keys corresponding to None values.
    """
    return {key: value for key, value in data.items() if value is not None}


class APIEditMixin:
    """A mixin that allows sane usage of Django's form machinery via the API.

    First it ensures that missing fields are not errors, then it removes
    None values from cleaned data. This means that missing fields result
    in no change instead of an error.
    """

    def full_clean(self):
        """For missing fields, default to the model's existing value."""
        self.data = get_overridden_query_dict(
            self.initial, self.data, self.fields)
        super(APIEditMixin, self).full_clean()

    def _post_clean(self):
        """Override Django's private hook _post_save to remove None values
        from 'self.cleaned_data'.

        _post_clean is where the fields of the instance get set with the data
        from self.cleaned_data.  That's why the cleanup needs to happen right
        before that.
        """
        self.cleaned_data = remove_None_values(self.cleaned_data)
        super(APIEditMixin, self)._post_clean()


class ModelForm(APIEditMixin, forms.ModelForm):
    """A form for editing models, with MAAS-specific behaviour.

    Specifically, it is much like Django's ``ModelForm``, but removes
    ``None`` values from cleaned data. This allows the forms to be used
    for both the UI and the API with unsuprising behaviour in both.
    """


def list_all_usable_architectures():
    """Return all architectures that can be used for nodes.

    These are the architectures for which any nodegroup has the boot images
    required to commission and install nodes.
    """
    # The Node edit form offers all usable architectures as options for the
    # architecture field.  Not all of these may be available in the node's
    # nodegroup, but to represent that accurately in the UI would depend on
    # the currently selected nodegroup.  Narrowing the options down further
    # would have to happen browser-side.
    architectures = set()
    for nodegroup in NodeGroup.objects.all():
        architectures = architectures.union(
            BootImage.objects.get_usable_architectures(nodegroup))
    return sorted(architectures)


def list_architecture_choices(architectures):
    """Return Django "choices" list for `architectures`."""
    # We simply return (name, name) as the choice for each architecture
    # here. We could do something more complicated to get a "nice"
    # label, but the truth is that architecture names are plenty
    # readable already.
    return [(arch, arch) for arch in architectures]


def pick_default_architecture(all_architectures):
    """Choose a default architecture, given a list of all usable ones.
    """
    if len(all_architectures) == 0:
        # Nothing we can do.
        return ''

    global_default = 'i386/generic'
    if global_default in all_architectures:
        # Generally, prefer basic i386.  It covers the most cases.
        return global_default
    else:
        # Failing that, just pick the first.
        return all_architectures[0]


class NodeForm(ModelForm):

    def __init__(self, request=None, *args, **kwargs):
        super(NodeForm, self).__init__(*args, **kwargs)
        # Even though it doesn't need it and doesn't use it, this form accepts
        # a parameter named 'request' because it is used interchangingly
        # with NodeAdminForm which actually uses this parameter.
        if kwargs.get('instance') is None:
            # Creating a new node.  Offer choice of nodegroup.
            self.fields['nodegroup'] = NodeGroupFormField(
                required=False, empty_label="Default (master)")
        self.set_up_architecture_field()

    def set_up_architecture_field(self):
        """Create the `architecture` field.

        This needs to be done on the fly so that we can pass a dynamic list of
        usable architectures.
        """
        architectures = list_all_usable_architectures()
        default_arch = pick_default_architecture(architectures)
        if len(architectures) == 0:
            choices = [BLANK_CHOICE]
        else:
            choices = list_architecture_choices(architectures)
        invalid_arch_message = compose_invalid_choice_text(
            'architecture', choices)
        self.fields['architecture'] = forms.ChoiceField(
            choices=choices, required=True, initial=default_arch,
            error_messages={'invalid_choice': invalid_arch_message})

    def clean_hostname(self):
        # Don't allow the hostname to be changed if the node is
        # currently allocated.  Juju knows the node by its old name, so
        # changing the name would confuse things.
        hostname = self.instance.hostname
        status = self.instance.status
        new_hostname = self.cleaned_data.get('hostname', hostname)
        if new_hostname != hostname and status == NODE_STATUS.ALLOCATED:
            raise ValidationError(
                "Can't change hostname to %s: node is in use." % new_hostname)

        return new_hostname

    def is_valid(self):
        is_valid = super(NodeForm, self).is_valid()
        if len(list_all_usable_architectures()) == 0:
            self.errors['architecture'] = (
                [NO_ARCHITECTURES_AVAILABLE])
            is_valid = False
        return is_valid

    distro_series = forms.ChoiceField(
        choices=DISTRO_SERIES_CHOICES, required=False,
        initial=DISTRO_SERIES.default,
        label="Release",
        error_messages={'invalid_choice': INVALID_DISTRO_SERIES_MESSAGE})

    hostname = forms.CharField(
        label="Host name", required=False, help_text=(
            "The FQDN (Fully Qualified Domain Name) is derived from the "
            "host name: If the cluster controller for this node is managing "
            "DNS then the domain part in the host name (if any) is replaced "
            "by the domain defined on the cluster; if the cluster controller "
            "does not manage DNS, then the host name as entered will be the "
            "FQDN."))

    class Meta:
        model = Node

        # Fields that the form should generate automatically from the
        # model:
        fields = (
            'hostname',
            'architecture',
            'distro_series',
            )


CLUSTER_NOT_AVAILABLE = mark_safe("""
The cluster controller for this node is not responding; power type
validation is not available.
""")


NO_ARCHITECTURES_AVAILABLE = mark_safe("""
No architectures are available to use for this node; boot images may not
have been imported on the selected cluster controller, or it may be
unavailable.
""")


class AdminNodeForm(NodeForm):
    """A `NodeForm` which includes fields that only an admin may change."""

    zone = forms.ModelChoiceField(
        label="Physical zone", required=False,
        initial=Zone.objects.get_default_zone,
        queryset=Zone.objects.all(), to_field_name='name')

    cpu_count = forms.IntegerField(
        required=False, initial=0, label="CPU Count")
    memory = forms.IntegerField(
        required=False, initial=0, label="Memory")
    storage = forms.IntegerField(
        required=False, initial=0, label="Disk space")

    class Meta:
        model = Node

        # Fields that the form should generate automatically from the
        # model:
        fields = NodeForm.Meta.fields + (
            'power_type',
            'power_parameters',
            'cpu_count',
            'memory',
            'storage',
        )

    def __init__(self, data=None, instance=None, request=None, **kwargs):
        super(AdminNodeForm, self).__init__(
            data=data, instance=instance, **kwargs)
        self.request = request
        self.set_up_initial_zone(instance)
        self.set_up_power_type(data, instance)
        # The zone field is not required because we want to be able
        # to omit it when using that form in the API.
        # We don't want the UI to show an entry for the 'empty' zone,
        # in the zones dropdown.  This is why we set 'empty_label' to
        # None to force Django not to display that empty entry.
        self.fields['zone'].empty_label = None

    def set_up_initial_zone(self, instance):
        """Initialise `zone` field if a node instance was given.

        This works around Django bug 17657: the zone field refers to a zone
        by name, not by ID, yet Django attempts to initialise it with an ID.
        That doesn't work, and so without this workaround the field would
        revert to the default zone.
        """
        if instance is not None:
            self.initial['zone'] = instance.zone.name

    def get_power_type(self, data, node):
        if data is None:
            data = {}

        power_type = data.get('power_type', self.initial.get('power_type'))

        # If power_type is None (this is a node creation form or this
        # form deals with an API call which does not change the value of
        # 'power_type') or invalid: get the node's current 'power_type'
        # value or the default value if this form is not linked to a node.

        if node is not None:
            nodegroups = [node.nodegroup]
        else:
            nodegroups = None

        try:
            power_types = get_power_types(nodegroups)
        except ClusterUnavailable as e:
            # If there's no request then this is an API call, so
            # there's no need to add a UI message, a suitable
            # ValidationError is raised elsewhere.
            if self.request is not None:
                messages.error(
                    self.request, CLUSTER_NOT_AVAILABLE + e.args[0])
            return ''

        if power_type not in power_types:
            if node is not None:
                power_type = node.power_type
            else:
                power_type = ''
        return power_type

    def set_up_power_type(self, data, node):
        """Set up the 'power_type' and 'power_parameters' fields.

        This can't be done at the model level because the choices need to
        be generated on the fly by get_power_type_choices().
        """
        power_type = self.get_power_type(data, node)
        choices = [BLANK_CHOICE] + get_power_type_choices()
        self.fields['power_type'] = forms.ChoiceField(
            required=False, choices=choices, initial=power_type)
        self.fields['power_parameters'] = get_power_type_parameters()[
            power_type]

    def _get_nodegroup(self):
        # This form is used for adding and editing nodes, and the
        # nodegroup field is the cleaned_data for the former and on the
        # instance for the latter.
        # The field is not present on the edit form because someone
        # decided that we should not let users move nodes between
        # nodegroups.  It is probably better to change that behaviour to
        # have a read-only field on the form.
        if self.instance.nodegroup is not None:
            return self.instance.nodegroup
        return self.cleaned_data['nodegroup']

    def clean(self):
        cleaned_data = super(AdminNodeForm, self).clean()
        # skip_check tells us to allow power_parameters to be saved
        # without any validation.  Nobody can remember why this was
        # added at this stage but it might have been a request from
        # smoser, we think.
        skip_check = (
            self.data.get('power_parameters_%s' % SKIP_CHECK_NAME) == 'true')
        # Try to contact the cluster controller; if it's down then we
        # prevent saving the form as we can't validate the power
        # parameters and type.
        if not skip_check:
            try:
                get_power_types([self._get_nodegroup()])
            except ClusterUnavailable as e:
                # Hey Django devs, this is a crap API to set errors.
                self._errors["power_type"] = self.error_class(
                    [CLUSTER_NOT_AVAILABLE + e.args[0]])
        # If power_type is not set and power_parameters_skip_check is not
        # on, reset power_parameters (set it to the empty string).
        no_power_type = cleaned_data.get('power_type', '') == ''
        if no_power_type and not skip_check:
            cleaned_data['power_parameters'] = ''
        return cleaned_data

    def save(self, *args, **kwargs):
        """Persist the node into the database."""
        node = super(AdminNodeForm, self).save(commit=False)
        zone = self.cleaned_data.get('zone')
        if zone:
            node.zone = zone
        if kwargs.get('commit', True):
            node.save(*args, **kwargs)
            self.save_m2m()  # Save many to many relations.
        return node


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
        except ValidationError as e:
            # Publish this error as a 'key' error rather than a 'general'
            # error because only the 'key' errors are displayed on the
            # 'add key' form.
            error = e.message_dict.pop('__all__')
            self._errors.setdefault('key', self.error_class()).extend(error)


class MultipleMACAddressField(forms.MultiValueField):

    def __init__(self, nb_macs=1, *args, **kwargs):
        fields = [MACAddressFormField() for i in range(nb_macs)]
        super(MultipleMACAddressField, self).__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            return data_list
        return []


def initialize_node_group(node, form_value=None):
    """If `node` is not in a node group yet, initialize it.

    The initial value is `form_value` if given, or the master nodegroup
    otherwise.
    """
    if node.nodegroup_id is not None:
        return
    if form_value is None:
        node.nodegroup = NodeGroup.objects.ensure_master()
    else:
        node.nodegroup = form_value


IP_BASED_HOSTNAME_REGEXP = re.compile('\d{1,3}-\d{1,3}-\d{1,3}-\d{1,3}')


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
            if MACAddress.objects.filter(mac_address=mac.lower()).exists():
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
        # As a side effect, this prevents editing of the node group on
        # an existing node.  It's all horribly dependent on the order of
        # calls in this class family, but Django doesn't seem to give us
        # a good way around it.
        initialize_node_group(node, self.cleaned_data.get('nodegroup'))
        node.save()
        for mac in self.cleaned_data['mac_addresses']:
            node.add_mac_address(mac)
        hostname = self.cleaned_data['hostname']
        stripped_hostname = strip_domain(hostname)
        # Generate a hostname for this node if the provided hostname is
        # IP-based (because this means that this name comes from a DNS
        # reverse query to the MAAS DNS) or an empty string.
        generate_hostname = (
            hostname == "" or
            IP_BASED_HOSTNAME_REGEXP.match(stripped_hostname) is not None)
        if generate_hostname:
            node.set_random_hostname()
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

    action = forms.ChoiceField(
        required=True,
        choices=[
            (action.name, action.display_bulk)
            for action in ACTION_CLASSES])

    # The name of the input button used with this form.
    input_name = 'action'

    def __init__(self, instance, *args, **kwargs):
        super(NodeActionForm, self).__init__(*args, **kwargs)
        self.node = instance
        self.actions = compile_node_actions(instance, self.user, self.request)
        self.action_buttons = self.actions.values()

    def display_message(self, message):
        """Show `message` as feedback after performing an action."""
        if self.request is not None:
            messages.add_message(self.request, messages.INFO, message)

    def clean_action(self):
        action_name = self.cleaned_data['action']
        # The field 'action' is required so 'action_name' will be None
        # here only if the field itself did not validate the data.
        if action_name is not None:
            action = self.actions.get(action_name)
            if action is None or not action.is_permitted():
                error_message = 'Not a permitted action: %s.' % action_name
                raise ValidationError(
                    {'action': [error_message]})
            if action is not None and action.inhibition is not None:
                raise ValidationError(
                    {'action': [action.inhibition]})
        return action_name

    def save(self, allow_redirect=True):
        """An action was requested.  Perform it.

        This implementation of `save` does not support the `commit` argument.
        """
        action_name = self.data.get('action')
        action = self.actions.get(action_name)
        message = action.execute(allow_redirect=allow_redirect)
        self.display_message(message)
        # Return updated node.
        return Node.objects.get(system_id=self.node.system_id)


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
        b"SpecificNodeActionForm", (NodeActionForm,),
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
                label="E-mail address", max_length=75, required=True))

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
        if User.objects.filter(email__iexact=email).exists():
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

    def clean(self):
        cleaned_data = super(Form, self).clean()
        for config_name in cleaned_data.keys():
            if config_name not in CONFIG_ITEMS_KEYS:
                self._errors[config_name] = self.error_class([
                    INVALID_SETTING_MSG_TEMPLATE % config_name])
        return cleaned_data

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
    maas_name = get_config_field('maas_name')
    enlistment_domain = get_config_field('enlistment_domain')
    http_proxy = get_config_field('http_proxy')
    upstream_dns = get_config_field('upstream_dns')
    ntp_server = get_config_field('ntp_server')


class ThirdPartyDriversForm(ConfigForm):
    """Settings page, Third Party Drivers section."""
    enable_third_party_drivers = get_config_field('enable_third_party_drivers')


class CommissioningForm(ConfigForm):
    """Settings page, Commissioning section."""
    check_compatibility = get_config_field('check_compatibility')
    commissioning_distro_series = forms.ChoiceField(
        choices=COMMISSIONING_DISTRO_SERIES_CHOICES, required=False,
        label="Default distro series used for commissioning",
        error_messages={'invalid_choice': compose_invalid_choice_text(
            'commissioning_distro_series',
            COMMISSIONING_DISTRO_SERIES_CHOICES)})


class UbuntuForm(ConfigForm):
    """Settings page, Ubuntu section."""
    default_distro_series = get_config_field('default_distro_series')
    main_archive = get_config_field('main_archive')
    ports_archive = get_config_field('ports_archive')


class GlobalKernelOptsForm(ConfigForm):
    """Settings page, Global Kernel Parameters section."""
    kernel_opts = get_config_field('kernel_opts')


class NodeGroupInterfaceForm(ModelForm):

    management = forms.TypedChoiceField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, required=False,
        coerce=int, empty_value=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT,
        help_text=(
            "If you enable DHCP management, you will need to install the "
            "'maas-dhcp' package on this cluster controller.  Similarly, you "
            "will need to install the 'maas-dns' package on this region "
            "controller to be able to enable DNS management."
            ))

    class Meta:
        model = NodeGroupInterface
        fields = (
            'interface',
            'management',
            'ip',
            'subnet_mask',
            'broadcast_ip',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
            )


class NodeGroupInterfaceForeignDHCPForm(ModelForm):
    """A form to update a nodegroupinterface's foreign_dhcp_ip field."""

    class Meta:
        model = NodeGroupInterface
        fields = (
            'foreign_dhcp_ip',
        )

    def save(self):
        foreign_dhcp_ip = self.cleaned_data['foreign_dhcp_ip']
        # Do this through an update, not a read/modify/write.  Updating
        # NodeGroupInterface client-side may inadvertently trigger Django
        # signals that cause a rewrite of the DHCP config, plus restart of
        # the DHCP server.
        # The inadvertent triggering has been known to happen because of race
        # conditions between read/modify/write transactions that were enabled
        # by Django defaulting to, and being designed for, the READ COMMITTED
        # isolation level; the ORM writing back even unmodified fields; and
        # GenericIPAddressField's default value being prone to problems where
        # NULL is sometimes represented as None, sometimes as an empty string,
        # and the difference being enough to convince the signal machinery
        # that these fields have changed when in fact they have not.
        query = NodeGroupInterface.objects.filter(id=self.instance.id)
        query.update(foreign_dhcp_ip=foreign_dhcp_ip)
        return NodeGroupInterface.objects.get(id=self.instance.id)


INTERFACES_VALIDATION_ERROR_MESSAGE = (
    "Invalid json value: should be a list of dictionaries, each containing "
    "the information needed to initialize an interface.")


# The DNS zone name used for nodegroups when none is explicitly provided.
DEFAULT_DNS_ZONE_NAME = 'maas'


def validate_nodegroupinterfaces_json(interfaces):
    """Check `NodeGroupInterface` definitions as found in a requst.

    This validates that the `NodeGroupInterface` definitions found in a
    request to `NodeGroupWithInterfacesForm` conforms to the expected basic
    structure: a list of dicts.

    :type interface: `dict` extracted from JSON request body.
    :raises ValidationError: If the interfaces definition is not a list of
        dicts as expected.
    """
    if not isinstance(interfaces, collections.Iterable):
        raise forms.ValidationError(INTERFACES_VALIDATION_ERROR_MESSAGE)
    for interface in interfaces:
        if not isinstance(interface, dict):
            raise forms.ValidationError(INTERFACES_VALIDATION_ERROR_MESSAGE)


def validate_nodegroupinterface_definition(interface):
    """Run a `NodeGroupInterface` definition through form validation.

    :param interface: Definition of a `NodeGroupInterface` as found in HTTP
        request data.
    :type interface: `dict` extracted from JSON request body.
    :raises ValidationError: If `NodeGroupInterfaceForm` finds the definition
        invalid.
    """
    form = NodeGroupInterfaceForm(data=interface)
    if not form.is_valid():
        raise forms.ValidationError(
            "Invalid interface: %r (%r)." % (interface, form._errors))


def validate_nonoverlapping_networks(interfaces):
    """Check against conflicting network ranges among interface definitions.

    :param interfaces: Iterable of interface definitions as found in HTTP
        request data.
    :raise ValidationError: If any two networks for entries of `interfaces`
        could potentially contain the same IP address.
    """
    unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
    managed_interfaces = [
        interface
        for interface in interfaces
        if interface.get('management', unmanaged) != unmanaged
        ]

    networks = [
        {
            'name': interface['interface'],
            'network': make_network(interface['ip'], interface['subnet_mask']),
        }
        for interface in managed_interfaces
        ]
    networks = sorted(networks, key=lambda network: network['network'].first)
    for index in range(1, len(networks)):
        start_of_this_network = networks[index]['network'].first
        end_of_last_network = networks[index - 1]['network'].last
        if start_of_this_network <= end_of_last_network:
            # IP ranges overlap.
            raise ValidationError(
                "Conflicting networks on %s and %s: address ranges overlap."
                % (networks[index - 1]['name'], networks[index]['name']))


class NodeGroupWithInterfacesForm(ModelForm):
    """Create a NodeGroup with unmanaged interfaces."""

    interfaces = forms.CharField(required=False)
    cluster_name = forms.CharField(required=False)

    class Meta:
        model = NodeGroup
        fields = (
            'cluster_name',
            'name',
            'uuid',
            )

    def __init__(self, status=None, *args, **kwargs):
        super(NodeGroupWithInterfacesForm, self).__init__(*args, **kwargs)
        self.status = status

    def clean_name(self):
        data = self.cleaned_data['name']
        if data == '':
            return DEFAULT_DNS_ZONE_NAME
        else:
            return data

    def clean(self):
        cleaned_data = super(NodeGroupWithInterfacesForm, self).clean()
        cluster_name = cleaned_data.get("cluster_name")
        uuid = cleaned_data.get("uuid")
        if uuid and not cluster_name:
            cleaned_data["cluster_name"] = (
                NODEGROUP_CLUSTER_NAME_TEMPLATE % {'uuid': uuid})
        return cleaned_data

    def clean_interfaces(self):
        data = self.cleaned_data['interfaces']
        # Stop here if the data is empty.
        if data == '':
            return data
        try:
            interfaces = json.loads(data)
        except ValueError:
            raise forms.ValidationError("Invalid json value.")

        validate_nodegroupinterfaces_json(interfaces)
        for interface in interfaces:
            validate_nodegroupinterface_definition(interface)

        validate_nonoverlapping_networks(interfaces)
        return interfaces

    def save(self):
        nodegroup = super(NodeGroupWithInterfacesForm, self).save()
        for interface in self.cleaned_data['interfaces']:
            instance = NodeGroupInterface(nodegroup=nodegroup)
            form = NodeGroupInterfaceForm(data=interface, instance=instance)
            form.save()
        if self.status is not None:
            nodegroup.status = self.status
            nodegroup.save()
        return nodegroup


class NodeGroupEdit(ModelForm):

    name = forms.CharField(
        label="DNS zone name",
        help_text=(
            "Name of the related DNS zone.  Note that this will only "
            "be used if MAAS is managing a DNS zone for one of the interfaces "
            "of this cluster.  See the 'status' of the interfaces below."),
        required=False)

    class Meta:
        model = NodeGroup
        fields = (
            'cluster_name',
            'status',
            'name',
            )

    def clean_name(self):
        old_name = self.instance.name
        new_name = self.cleaned_data['name']
        if new_name == old_name or not new_name:
            # No change to the name.  Return old name.
            return old_name

        if not self.instance.manages_dns():
            # Not managing DNS.  There won't be any DNS problems with this
            # name change then.
            return new_name

        nodes_in_use = Node.objects.filter(
            nodegroup=self.instance, status=NODE_STATUS.ALLOCATED)
        if nodes_in_use.exists():
            raise ValidationError(
                "Can't rename DNS zone to %s; nodes are in use." % new_name)

        return new_name


class TagForm(ModelForm):

    class Meta:
        model = Tag
        fields = (
            'name',
            'comment',
            'definition',
            'kernel_opts',
            )

    def clean_definition(self):
        definition = self.cleaned_data['definition']
        if not definition:
            return ""
        try:
            etree.XPath(definition)
        except etree.XPathSyntaxError as e:
            msg = 'Invalid xpath expression: %s' % (e,)
            raise ValidationError({'definition': [msg]})
        return definition


class CommissioningScriptForm(forms.Form):

    content = forms.FileField(
        label="Commissioning script", allow_empty_file=False)

    def __init__(self, instance=None, *args, **kwargs):
        super(CommissioningScriptForm, self).__init__(*args, **kwargs)

    def clean_content(self):
        content = self.cleaned_data['content']
        name = content.name
        if pipes.quote(name) != name:
            raise forms.ValidationError(
                "Name contains disallowed characters (e.g. space or quotes).")
        if CommissioningScript.objects.filter(name=name).exists():
            raise forms.ValidationError(
                "A script with that name already exists.")
        return content

    def save(self, *args, **kwargs):
        content = self.cleaned_data['content']
        CommissioningScript.objects.create(
            name=content.name,
            content=Bin(content.read()))


class UnconstrainedMultipleChoiceField(MultipleChoiceField):
    """A MultipleChoiceField which does not constrain the given choices."""

    def validate(self, value):
        return value


class ValidatorMultipleChoiceField(MultipleChoiceField):
    """A MultipleChoiceField validating each given choice with a validator."""

    def __init__(self, validator, **kwargs):
        super(ValidatorMultipleChoiceField, self).__init__(**kwargs)
        self.validator = validator

    def validate(self, values):
        for value in values:
            self.validator(value)
        return values


class InstanceListField(UnconstrainedMultipleChoiceField):
    """A multiple-choice field used to list model instances."""

    def __init__(self, model_class, field_name,
                 text_for_invalid_object=None,
                 *args, **kwargs):
        """Instantiate an InstanceListField.

        Build an InstanceListField to deal with a list of instances of
        the class `model_class`, identified their field named
        `field_name`.

        :param model_class:  The model class of the instances to list.
        :param field_name:  The name of the field used to retrieve the
            instances. This must be a unique field of the `model_class`.
        :param text_for_invalid_object:  Option error message used to
            create the validation error returned when any of the input
            values doesn't match an existing object.  The default value
            is "Unknown {obj_name}(s): {unknown_names}.".  A custom
            message can use {obj_name} and {unknown_names} which will be
            replaced by the name of the model instance and the list of
            the names that didn't correspond to a valid instance
            respectively.
        """
        super(InstanceListField, self).__init__(*args, **kwargs)
        self.model_class = model_class
        self.field_name = field_name
        if text_for_invalid_object is None:
            text_for_invalid_object = (
                "Unknown {obj_name}(s): {unknown_names}.")
        self.text_for_invalid_object = text_for_invalid_object

    def clean(self, value):
        """Clean the list of field values.

        Assert that each field value corresponds to an instance of the class
        `self.model_class`.
        """
        if value is None:
            return None
        # `value` is in fact a list of values since this field is a subclass of
        # forms.MultipleChoiceField.
        set_values = set(value)
        filters = {'%s__in' % self.field_name: set_values}

        instances = self.model_class.objects.filter(**filters)
        if len(instances) != len(set_values):
            unknown = set_values.difference(
                {getattr(instance, self.field_name) for instance in instances})
            error = self.text_for_invalid_object.format(
                obj_name=self.model_class.__name__.lower(),
                unknown_names=', '.join(sorted(unknown))
                )
            raise forms.ValidationError(error)
        return instances


class SetZoneBulkAction:
    """A custom action we only offer in bulk: "Set physical zone."

    Looks just enough like a node action class for presentation purposes, but
    isn't one of the actions we normally offer on the node page.  The
    difference is that this action takes an argument: the zone.
    """
    name = 'set_zone'
    display_bulk = "Set physical zone"


class BulkNodeActionForm(forms.Form):
    # system_id is a multiple-choice field so it can actually contain
    # a list of system ids.
    system_id = UnconstrainedMultipleChoiceField()

    def __init__(self, user, *args, **kwargs):
        super(BulkNodeActionForm, self).__init__(*args, **kwargs)
        self.user = user
        action_choices = (
            # Put an empty action as the first displayed option to avoid
            # fat-fingered bulk actions.
            [('', '')] +
            [(action.name, action.display_bulk) for action in ACTION_CLASSES]
            )
        add_zone_field = (
            user.is_superuser and
            (
                self.data == {} or
                self.data.get('action') == SetZoneBulkAction.name
            )
        )
        # Only admin users get the "set zone" bulk action.
        # The 'zone' field is required only if the form is being submitted
        # with the 'action' set to SetZoneBulkAction.name or when the UI is
        # rendering a GET request (i.e. the zone cannot be the empty string).
        # Thus it cannot be added to the form when the form is being
        # submitted with an action other than SetZoneBulkAction.name.
        if add_zone_field:
            action_choices.append(
                (SetZoneBulkAction.name, SetZoneBulkAction.display_bulk))
            # This adds an input field: the zone.
            self.fields['zone'] = forms.ModelChoiceField(
                label="Physical zone", required=True,
                initial=Zone.objects.get_default_zone(),
                queryset=Zone.objects.all(), to_field_name='name')
        self.fields['action'] = forms.ChoiceField(
            required=True, choices=action_choices)

    def clean_system_id(self):
        system_ids = self.cleaned_data['system_id']
        # Remove duplicates.
        system_ids = set(system_ids)
        if len(system_ids) == 0:
            raise forms.ValidationError("No node selected.")
        # Validate all the system ids.
        real_node_count = Node.objects.filter(
            system_id__in=system_ids).count()
        if real_node_count != len(system_ids):
            raise forms.ValidationError(
                "Some of the given system ids are invalid system ids.")
        return system_ids

    def perform_action(self, action_name, system_ids):
        """Perform a node action on the identified nodes.

        :param action_name: Name of a node action in `ACTIONS_DICT`.
        :param system_ids: Iterable of `Node.system_id` values.
        :return: A tuple as returned by `save`.
        """
        action_class = ACTIONS_DICT.get(action_name)
        not_actionable = 0
        not_permitted = 0
        done = 0
        for system_id in system_ids:
            node = Node.objects.get(system_id=system_id)
            if node.status in action_class.actionable_statuses:
                action_instance = action_class(node=node, user=self.user)
                if action_instance.inhibit() is not None:
                    not_actionable += 1
                else:
                    if action_instance.is_permitted():
                        # Do not let execute() raise a redirect exception
                        # because this action is part of a bulk operation.
                        action_instance.execute(allow_redirect=False)
                        done += 1
                    else:
                        not_permitted += 1
            else:
                not_actionable += 1
        return done, not_actionable, not_permitted

    def get_selected_zone(self):
        """Return the zone which the user has selected (or `None`).

        Used for the "set zone" bulk action.
        """
        zone_name = self.cleaned_data['zone']
        if zone_name is None or zone_name == '':
            return None
        else:
            return Zone.objects.get(name=zone_name)

    def set_zone(self, system_ids):
        """Custom bulk action: set zone on identified nodes.

        :return: A tuple as returned by `save`.
        """
        zone = self.get_selected_zone()
        Node.objects.filter(system_id__in=system_ids).update(zone=zone)
        return (len(system_ids), 0, 0)

    def save(self, *args, **kwargs):
        """Perform the action on the selected nodes.

        This method returns a tuple containing 3 elements: the number of
        nodes for which the action was successfully performed, the number of
        nodes for which the action could not be performed because that
        transition was not allowed and the number of nodes for which the
        action could not be performed because the user does not have the
        required permission.
        """
        action_name = self.cleaned_data['action']
        system_ids = self.cleaned_data['system_id']
        if action_name == SetZoneBulkAction.name:
            return self.set_zone(system_ids)
        else:
            return self.perform_action(action_name, system_ids)


class DownloadProgressForm(ModelForm):
    """Form to update a `DownloadProgress`.

    The `get_download` helper will find the right progress record to update,
    or create one if needed.
    """

    class Meta:
        model = DownloadProgress
        fields = (
            'size',
            'bytes_downloaded',
            'error',
            )

    @staticmethod
    def get_download(nodegroup, filename, bytes_downloaded):
        """Find or create a `DownloadProgress` to update.

        Will create a new `DownloadProgress` if appropriate.  Use the form
        to update its fields.

        This returns `None` in exactly one situation: if `bytes_downloaded`
        is not `None`, but there was no existing record of the download.
        That is not something that will happen in proper usage.
        """
        if bytes_downloaded is None:
            # This is a new download.  Create a new DownloadProgress.
            return DownloadProgress.objects.create(
                nodegroup=nodegroup, filename=filename)
        else:
            # This is an ongoing download.  Update the existing one.
            return DownloadProgress.objects.get_latest_download(
                nodegroup, filename)

    def clean(self):
        if self.instance.id is None:
            # The form was left to create its own DownloadProgress.  This can
            # only happen if get_download returned None, which in turn can only
            # happen in this particular scenario.
            raise ValidationError(
                "bytes_downloaded was passed on a new download.")

        return super(DownloadProgressForm, self).clean()


class ZoneForm(ModelForm):

    class Meta:
        model = Zone
        fields = (
            'name',
            'description',
            )

    def clean_name(self):
        new_name = self.cleaned_data['name']
        renaming_instance = (
            self.instance is not None and self.instance.is_default() and
            self.instance.name != new_name)
        if renaming_instance:
            raise forms.ValidationError(
                "This zone is the default zone, it cannot be renamed.")
        return self.cleaned_data['name']


class NodeMACAddressChoiceField(forms.ModelMultipleChoiceField):
    """A ModelMultipleChoiceField which shows the name of the MACs."""

    def label_from_instance(self, obj):
        return "%s (%s)" % (obj.mac_address, obj.node.hostname)


class NetworkForm(ModelForm):

    class Meta:
        model = Network
        fields = (
            'name',
            'description',
            'ip',
            'netmask',
            'vlan_tag',
            )

    mac_addresses = NodeMACAddressChoiceField(
        label="Connected network interface cards",
        queryset=MACAddress.objects.all().order_by(
            'node__hostname', 'mac_address'),
        required=False,
        to_field_name='mac_address',
        widget=forms.SelectMultiple(attrs={'size': 10}),
        )

    def __init__(self, data=None, instance=None, **kwargs):
        super(NetworkForm, self).__init__(
            data=data, instance=instance, **kwargs)
        self.set_up_initial_macaddresses(instance)

    def set_up_initial_macaddresses(self, instance):
        """Set the initial value for the field 'macaddresses'.
        This is to work around Django bug 17657: the initial value for fields
        of type ModelMultipleChoiceField which use 'to_field_name', when it
        is extracted from the provided instance object, is not
        properly computed.
        """
        if instance is not None:
            name = self.fields['mac_addresses'].to_field_name
            self.initial['mac_addresses'] = [
                getattr(obj, name) for obj in instance.macaddress_set.all()]

    def save(self, *args, **kwargs):
        """Persist the network into the database."""
        network = super(NetworkForm, self).save(*args, **kwargs)
        macaddresses = self.cleaned_data.get('mac_addresses')
        if macaddresses is not None:
            network.macaddress_set.clear()
            network.macaddress_set.add(*macaddresses)
        return network


class NetworksListingForm(forms.Form):
    """Form for the networks listing API."""

    # Multi-value parameter, but with a name in the singular.  This is going
    # to be passed as a GET-style parameter in the URL, so repeated as "node="
    # for every node.
    node = InstanceListField(
        model_class=Node, field_name='system_id',
        label="Show only networks that are attached to all of these nodes.",
        required=False, error_messages={
            'invalid_list':
            "Invalid parameter: list of node system IDs required.",
            })

    def filter_networks(self, networks):
        """Filter (and order) the given networks by the form's criteria.

        :param networks: A query set of :class:`Network`.
        :return: A version of `networks` restricted and ordered according to
            the criteria passed to the form.
        """
        nodes = self.cleaned_data.get('node')
        if nodes is not None:
            for node in nodes:
                networks = networks.filter(macaddress__node=node)
        return networks.order_by('name')


class MACsForm(forms.Form):
    """Base form with a list of MAC addresses."""

    macs = InstanceListField(
        model_class=MACAddress, field_name='mac_address',
        label="MAC addresses to be connected/disconnected.", required=True,
        text_for_invalid_object="Unknown MAC address(es): {unknown_names}.",
        error_messages={
            'invalid_list':
            "Invalid parameter: list of node MAC addresses required.",
            })

    def __init__(self, network, *args, **kwargs):
        super(MACsForm, self).__init__(*args, **kwargs)
        self.network = network

    def get_macs(self):
        """Return `MACAddress` objects matching the `macs` parameter."""
        return self.cleaned_data.get('macs')


class NetworkConnectMACsForm(MACsForm):
    """Form for the `Network` `connect_macs` API call."""

    def save(self):
        """Connect the MAC addresses to the form's network."""
        self.network.macaddress_set.add(*self.get_macs())


class NetworkDisconnectMACsForm(MACsForm):
    """Form for the `Network` `disconnect_macs` API call."""

    def save(self):
        """Disconnect the MAC addresses from the form's network."""
        self.network.macaddress_set.remove(*self.get_macs())
