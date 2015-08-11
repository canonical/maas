# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    "BootSourceForm",
    "BootSourceSelectionForm",
    "BootSourceSettingsForm",
    "BulkNodeActionForm",
    "create_Network_from_NodeGroupInterface",
    "ClaimIPForMACForm",
    "CommissioningForm",
    "CommissioningScriptForm",
    "DownloadProgressForm",
    "get_action_form",
    "get_node_edit_form",
    "get_node_create_form",
    "list_all_usable_architectures",
    "StorageSettingsForm",
    "MAASAndNetworkForm",
    "MACAddressForm",
    "NetworkConnectMACsForm",
    "NetworkDisconnectMACsForm",
    "NetworkForm",
    "NetworksListingForm",
    "NodeGroupEdit",
    "NodeGroupInterfaceForm",
    "NodeGroupDefineForm",
    "NodeWithMACAddressesForm",
    "CreatePhysicalBlockDeviceForm",
    "ReleaseIPForm",
    "SSHKeyForm",
    "SSLKeyForm",
    "TagForm",
    "ThirdPartyDriversForm",
    "UbuntuForm",
    "ZoneForm",
    ]

import collections
from collections import Counter
from functools import partial
import json
import pipes
from random import randint
import re

from crochet import TimeoutError
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
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import connection
from django.db.utils import IntegrityError
from django.forms import (
    CheckboxInput,
    Form,
    MultipleChoiceField,
)
from django.utils.safestring import mark_safe
from lxml import etree
from maasserver.api.utils import get_overridden_query_dict
from maasserver.clusterrpc.osystems import (
    validate_license_key,
    validate_license_key_for,
)
from maasserver.clusterrpc.power_parameters import (
    get_power_type_choices,
    get_power_type_parameters,
    get_power_types,
)
from maasserver.config_forms import SKIP_CHECK_NAME
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    CACHE_MODE_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_GROUP_RAID_TYPE_CHOICES,
    FILESYSTEM_TYPE,
    NODE_BOOT,
    NODE_BOOT_CHOICES,
    NODE_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
)
from maasserver.exceptions import (
    ClusterUnavailable,
    NodeActionError,
)
from maasserver.fields import (
    LargeObjectFile,
    MACAddressFormField,
    NodeGroupFormField,
)
from maasserver.forms_settings import (
    CONFIG_ITEMS_KEYS,
    get_config_field,
    INVALID_SETTING_MSG_TEMPLATE,
    validate_missing_boot_images,
)
from maasserver.models import (
    Bcache,
    BlockDevice,
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    BootSourceCache,
    BootSourceSelection,
    Config,
    Device,
    DownloadProgress,
    Filesystem,
    LargeFile,
    LicenseKey,
    MACAddress,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    Partition,
    PartitionTable,
    PhysicalBlockDevice,
    RAID,
    Space,
    SSHKey,
    SSLKey,
    Tag,
    VirtualBlockDevice,
    VolumeGroup,
    Zone,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.node import (
    fqdn_is_duplicate,
    nodegroup_fqdn,
)
from maasserver.models.nodegroup import NODEGROUP_CLUSTER_NAME_TEMPLATE
from maasserver.models.subnet import (
    create_cidr,
    Subnet,
)
from maasserver.node_action import (
    ACTION_CLASSES,
    ACTIONS_DICT,
    compile_node_actions,
)
from maasserver.utils import strip_domain
from maasserver.utils.converters import machine_readable_bytes
from maasserver.utils.forms import (
    compose_invalid_choice_text,
    set_form_error,
)
from maasserver.utils.interfaces import (
    get_name_and_vlan_from_cluster_interface,
    make_name_from_interface,
)
from maasserver.utils.orm import (
    get_one,
    transactional,
)
from maasserver.utils.osystems import (
    get_distro_series_initial,
    get_release_requires_key,
    list_all_releases_requiring_keys,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_osystem_choices,
    list_release_choices,
)
from metadataserver.fields import Bin
from metadataserver.models import CommissioningScript
from netaddr import (
    AddrFormatError,
    IPAddress,
    IPNetwork,
    IPRange,
    valid_ipv6,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.network import REVEAL_IPv6
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.utils.network import (
    ip_range_within_network,
    make_network,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
)
from twisted.internet.defer import DeferredList
from twisted.internet.task import coiterate
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure


maaslog = get_maas_logger()

# A reusable null-option for choice fields.
BLANK_CHOICE = ('', '-------')

SUBNET_MASK_HELP = "e.g. 255.255.255.0 (defaults to 64-bit netmask for IPv6)."


def _make_network_from_subnet(ip, subnet):
    return make_network(ip, IPNetwork(subnet.cidr).netmask)


def remove_None_values(data):
    """Return a new dictionary without the keys corresponding to None values.
    """
    return {key: value for key, value in data.items() if value is not None}


class APIEditMixin:
    """A mixin that allows sane usage of Django's form machinery via the API.

    First it ensures that missing fields are not errors, then it removes
    None values from cleaned data. This means that missing fields result
    in no change instead of an error.

    :ivar submitted_data: The `data` as originally submitted.
    """

    def full_clean(self):
        """For missing fields, default to the model's existing value."""
        self.submitted_data = self.data
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


class MAASModelForm(APIEditMixin, forms.ModelForm):
    """A form for editing models, with MAAS-specific behaviour.

    Specifically, it is much like Django's ``ModelForm``, but removes
    ``None`` values from cleaned data. This allows the forms to be used
    for both the UI and the API with unsuprising behaviour in both.

    With some fields (like boolean fields), the behavior of a UI-submitted
    form and a API-submitted form needs to be different: the UI will omit
    the field to denote "false" where the API will provide the existing
    value for the field.

    Each form needs to deal with this but this base class provides built-in
    support for marking that a form is used in the UI by passing a
    'ui_submission=True' parameter; this information can then be used by the
    form to specialize its behavior depending on whether the submission is
    made from the API or the UI.
    """

    def __init__(self, data=None, files=None, ui_submission=False, **kwargs):
        super(MAASModelForm, self).__init__(data=data, files=files, **kwargs)
        if ui_submission:
            # Add the ui_submission field.  Insert it before the other fields,
            # so that the field validators will have access to it regardless of
            # whether their fields were defined before or after this one.
            ui_submission_field = (
                'ui_submission',
                forms.CharField(widget=forms.HiddenInput(), required=False),
                )
            # Django 1.6 and earlier use their own SortedDict class; 1.7 uses
            # the standard library's OrderedDict.  The differences are
            # deprecated in 1.6, but to be on the safe side we'll use whichever
            # class is actually being used.
            dict_type = self.fields.__class__
            self.fields = dict_type(
                [ui_submission_field] + list(self.fields.items()))


def list_all_usable_architectures():
    """Return all architectures that can be used for nodes.

    These are the architectures for which any boot resource exists. Now that
    all clusters sync from the region, all cluster support the same
    architectures.
    """
    return sorted(BootResource.objects.get_usable_architectures())


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


def clean_distro_series_field(form, field, os_field):
    """Cleans the distro_series field in the form. Validating that
    the selected operating system matches the distro_series.

    :param form: `Form` class
    :param field: distro_series field name
    :param os_field: osystem field name
    :return: clean distro_series field value
    """
    new_distro_series = form.cleaned_data.get(field)
    if '*' in new_distro_series:
        new_distro_series = new_distro_series.replace('*', '')
    if new_distro_series is None or '/' not in new_distro_series:
        return new_distro_series
    os, release = new_distro_series.split('/', 1)
    if os_field in form.cleaned_data:
        new_os = form.cleaned_data[os_field]
        if os != new_os:
            raise ValidationError(
                "%s in %s does not match with "
                "operating system %s" % (release, field, os))
    return release


def find_osystem_and_release_from_release_name(name):
    """Return os and release for the given release name."""
    osystems = list_all_usable_osystems()
    for osystem in osystems:
        for release in osystem['releases']:
            if release['name'] == name:
                return osystem, release
    return None, None


def contains_managed_ipv6_interface(interfaces):
    """Does any of a list of cluster interfaces manage a IPv6 subnet?"""
    return any(
        interface.manages_static_range() and valid_ipv6(interface.ip)
        for interface in interfaces
        )


class CheckboxInputTrueDefault(CheckboxInput):
    """A CheckboxInput widget with 'True' as its default value.

    The default CheckboxInput assumes its default is 'False'.  This isn't
    a problem when the widget is used in the UI because the underlying model's
    "default" can override this but since we're using this widget to handle
    API's requests as well, we need to work around this limitation.
    """
    def value_from_datadict(self, data, files, name):
        if name not in data:
            return True
        else:
            return super(CheckboxInput, self).value_from_datadict(
                data, files, name)


class NodeForm(MAASModelForm):

    def _release_a_newer_than_b(self, a, b):
        """ Compare two Ubuntu releases and return true if a >= b

        The release names can be the full release name(e.g Precise, Trusty), or
        a hardware enablement(e.g hwe-p, hwe-t). The function wraps around the
        letter 'p' as Precise was the first version of Ubuntu MAAS supported
        """
        def get_release_num(release):
            release = release.lower()
            if 'hwe-' in release:
                release = release.lstrip('hwe-')
            return ord(release[0])

        # Compare release versions based off of the first letter of their
        # release name or the letter in hwe-<letter>. Wrap around the letter
        # 'p' as that is the first version of Ubuntu MAAS supported.
        num_a = get_release_num(a)
        num_b = get_release_num(b)
        num_wrap = ord('p')

        if((num_a >= num_wrap and num_b >= num_wrap and num_a >= num_b) or
           (num_a < num_wrap and num_b >= num_wrap and num_a < num_b) or
           (num_a < num_wrap and num_b < num_wrap and num_a >= num_b)):
            return True
        else:
            return False

    def _clean_hwe_kernel(self):
        hwe_kernel = self.cleaned_data.get('hwe_kernel')
        min_hwe_kernel = self.cleaned_data.get('min_hwe_kernel')
        architecture = self.cleaned_data.get('architecture')
        osystem = self.cleaned_data.get('osystem')
        distro_series = self.cleaned_data.get('distro_series')

        # The hwe_kernel feature is only supported on Ubuntu
        if((osystem and "ubuntu" not in osystem.lower()) or
           (not architecture or architecture == '') or
           (not distro_series or distro_series == '')):
            return hwe_kernel

        arch, subarch = architecture.split('/')

        if (subarch != 'generic' and
            (hwe_kernel.startswith('hwe-') or
             min_hwe_kernel.startswith('hwe-'))):
            set_form_error(
                self, 'hwe_kernel',
                'Subarchitecture(%s) must be generic when setting hwe_kernel.'
                % subarch)
            return

        os_release = osystem + '/' + distro_series
        usable_kernels = BootResource.objects.get_usable_kernels(
            os_release, arch)

        if hwe_kernel.startswith('hwe-'):
            if hwe_kernel not in usable_kernels:
                set_form_error(
                    self, 'hwe_kernel',
                    '%s is not avaliable for %s on %s.' %
                    (hwe_kernel, os_release, architecture))
                return
            if not self._release_a_newer_than_b(hwe_kernel, distro_series):
                set_form_error(
                    self, 'hwe_kernel',
                    '%s is too old to use on %s.' % (hwe_kernel, os_release))
                return

        if(hwe_kernel.startswith('hwe-') and
           min_hwe_kernel.startswith('hwe-') and
           not self._release_a_newer_than_b(hwe_kernel, min_hwe_kernel)):
            set_form_error(
                self, 'hwe_kernel',
                'hwe_kernel(%s) is older than min_hwe_kernel(%s).' %
                (hwe_kernel, min_hwe_kernel))
            return
        elif(min_hwe_kernel.startswith('hwe-')):
            for i in usable_kernels:
                if self._release_a_newer_than_b(i, min_hwe_kernel):
                    return i
            set_form_error(
                self, 'hwe_kernel',
                '%s has no kernels availible which meet min_hwe_kernel(%s).' %
                (distro_series, min_hwe_kernel))
            return
        elif hwe_kernel.strip() == '':
            return 'hwe-' + distro_series[0]

        return hwe_kernel

    def __init__(self, request=None, *args, **kwargs):
        super(NodeForm, self).__init__(*args, **kwargs)
        # Even though it doesn't need it and doesn't use it, this form accepts
        # a parameter named 'request' because it is used interchangingly
        # with NodeAdminForm which actually uses this parameter.

        instance = kwargs.get('instance')
        if instance is None or instance.owner is None:
            self.has_owner = False
        else:
            self.has_owner = True

        # Are we creating a new node object?
        self.new_node = (instance is None)
        if self.new_node:
            # Offer choice of nodegroup.
            self.fields['nodegroup'] = NodeGroupFormField(
                required=False, empty_label="Default (master)")

        if not REVEAL_IPv6:
            # We're not showing the IPv6 feature to the user.  Hide the ability
            # to disable IPv4 on a node.
            allow_disable_ipv4 = False
        elif self.new_node:
            # Permit disabling of IPv4 if at least one cluster supports IPv6.
            allow_disable_ipv4 = contains_managed_ipv6_interface(
                NodeGroupInterface.objects.all())
        else:
            # Permit disabling of IPv4 if at least one interface on the cluster
            # supports IPv6.
            allow_disable_ipv4 = contains_managed_ipv6_interface(
                self.instance.nodegroup.nodegroupinterface_set.all())

        self.set_up_architecture_field()
        self.set_up_osystem_and_distro_series_fields(instance)

        if not allow_disable_ipv4:
            # Hide the disable_ipv4 field until support works properly.  The
            # API will still support the field, but it won't be visible.
            # This hidden field absolutely needs an empty label, because its
            # input widget may be hidden but its label is not!
            #
            # To enable the field, just remove this clause.
            self.fields['disable_ipv4'] = forms.BooleanField(
                label="", required=False, widget=forms.HiddenInput())

        # We only want the license key field to render in the UI if the `OS`
        # and `Release` fields are also present.
        if self.has_owner:
            self.fields['license_key'] = forms.CharField(
                label="License Key", required=False, help_text=(
                    "License key for operating system"),
                max_length=30)
        else:
            self.fields['license_key'] = forms.CharField(
                label="", required=False, widget=forms.HiddenInput())

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
            choices=choices, required=False, initial=default_arch,
            error_messages={'invalid_choice': invalid_arch_message})

    def set_up_osystem_and_distro_series_fields(self, instance):
        """Create the `osystem` and `distro_series` fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        usable operating systems and distro_series.
        """
        osystems = list_all_usable_osystems()
        releases = list_all_usable_releases(osystems)
        if self.has_owner:
            os_choices = list_osystem_choices(osystems)
            distro_choices = list_release_choices(releases)
            invalid_osystem_message = compose_invalid_choice_text(
                'osystem', os_choices)
            invalid_distro_series_message = compose_invalid_choice_text(
                'distro_series', distro_choices)
            self.fields['osystem'] = forms.ChoiceField(
                label="OS", choices=os_choices, required=False, initial='',
                error_messages={'invalid_choice': invalid_osystem_message})
            self.fields['distro_series'] = forms.ChoiceField(
                label="Release", choices=distro_choices,
                required=False, initial='',
                error_messages={
                    'invalid_choice': invalid_distro_series_message})
        else:
            self.fields['osystem'] = forms.ChoiceField(
                label="", required=False, widget=forms.HiddenInput())
            self.fields['distro_series'] = forms.ChoiceField(
                label="", required=False, widget=forms.HiddenInput())
        if instance is not None:
            initial_value = get_distro_series_initial(osystems, instance)
            if instance is not None:
                self.initial['distro_series'] = initial_value

    def clean_hostname(self):
        # XXX 2014-08-14 jason-hobbs, bug=1356880; MAAS shouldn't allow
        # a hostname to be changed on a "deployed" node, but it doesn't
        # yet have the ability to distinguish between an "acquired" node
        # and a "deployed" node.

        new_hostname = self.cleaned_data.get('hostname')

        # XXX 2014-07-30 jason-hobbs, bug=1350459: This check for no
        # nodegroup shouldn't be necessary, but many tests don't provide
        # a nodegroup to NodeForm.
        if self.instance.nodegroup is None:
            return new_hostname

        if self.instance.nodegroup.manages_dns():
            new_fqdn = nodegroup_fqdn(
                new_hostname, self.instance.nodegroup.name)
        else:
            new_fqdn = new_hostname
        if fqdn_is_duplicate(self.instance, new_fqdn):
            raise ValidationError(
                "Node with FQDN '%s' already exists." % (new_fqdn))

        return new_hostname

    def clean_distro_series(self):
        return clean_distro_series_field(self, 'distro_series', 'osystem')

    def clean_disable_ipv4(self):
        # Boolean fields only show up in UI form submissions as "true" (if the
        # box was checked) or not at all (if the box was not checked).  This
        # is different from API submissions which can submit "false" values.
        # Our forms are rigged to interpret missing fields as unchanged, but
        # that doesn't work for the UI.  A form in the UI always submits all
        # its fields, so in that case, no value means False.
        #
        # To kludge around this, the UI form submits a hidden input field named
        # "ui_submission" that doesn't exist in the API.  If this field is
        # present, go with the UI-style behaviour.
        form_data = self.submitted_data
        if 'ui_submission' in form_data and 'disable_ipv4' not in form_data:
            self.cleaned_data['disable_ipv4'] = False
        return self.cleaned_data['disable_ipv4']

    def clean_swap_size(self):
        """Validates the swap size field and parses integers suffixed with K,
        M, G and T
        """
        swap_size = self.cleaned_data.get('swap_size')
        if swap_size == '':
            return None
        elif swap_size.endswith('K'):
            return int(swap_size[:-1]) * 1000
        elif swap_size.endswith('M'):
            return int(swap_size[:-1]) * 1000000
        elif swap_size.endswith('G'):
            return int(swap_size[:-1]) * 1000000000
        elif swap_size.endswith('T'):
            return int(swap_size[:-1]) * 1000000000000
        try:
            return int(swap_size)
        except ValueError:
            raise ValidationError('Invalid size for swap: %s' % swap_size)

    def clean_boot_type(self):
        boot_type = self.cleaned_data.get('boot_type')
        if not boot_type:
            return NODE_BOOT.FASTPATH
        else:
            return boot_type

    def clean(self):
        cleaned_data = super(NodeForm, self).clean()
        if self.new_node and self.data.get('disable_ipv4') is None:
            # Creating a new node, without a value for disable_ipv4 given.
            # Take the default value from the node's cluster.
            nodegroup = cleaned_data['nodegroup']
            cleaned_data['disable_ipv4'] = nodegroup.default_disable_ipv4
        cleaned_data['hwe_kernel'] = self._clean_hwe_kernel()
        return cleaned_data

    def is_valid(self):
        is_valid = super(NodeForm, self).is_valid()
        if not is_valid:
            return False
        if len(list_all_usable_architectures()) == 0:
            set_form_error(
                self, "architecture", NO_ARCHITECTURES_AVAILABLE)
            is_valid = False
        return is_valid

    def clean_license_key(self):
        """Validates the license_key field is the correct format for the
        selected operating system."""
        # We allow the license_key field to be blank, even if the OS requires
        # a license key. This is to allow for situations where the OS has a
        # license key installed in the image that gets deployed, or where the
        # OS is activated using some other activation service (for example
        # Windows KMS activation).
        key = self.cleaned_data.get('license_key')
        if key == '':
            return ''

        os_name = self.cleaned_data.get('osystem')
        series = self.cleaned_data.get('distro_series')
        if os_name == '':
            return ''

        # Without a nodegroup then all nodegroups need to be used to validate
        # the license key.
        if self.instance.nodegroup is None:
            if not validate_license_key(os_name, series, key):
                raise ValidationError("Invalid license key.")
            return key

        # Validate the license key for the specific nodegroup.
        try:
            is_valid = validate_license_key_for(
                self.instance.nodegroup, os_name, series, key)
        except (NoConnectionsAvailable, TimeoutError):
            raise ValidationError(
                "Could not contact cluster '%s' to validate license key; "
                "please try again later." %
                self.instance.nodegroup.name)
        except NoSuchOperatingSystem:
            raise ValidationError(
                "Cluster '%s' does not support the operating system '%s'" % (
                    self.instance.nodegroup.name, os_name))
        if not is_valid:
            raise ValidationError("Invalid license key.")
        return key

    def set_distro_series(self, series=''):
        """Sets the osystem and distro_series, from the provided
        distro_series.
        """
        # This implementation is used so that current API, is not broken. This
        # makes the distro_series a flat namespace. The distro_series is used
        # to search through the supporting operating systems, to find the
        # correct operating system that supports this distro_series.
        self.is_bound = True
        self.data['osystem'] = ''
        self.data['distro_series'] = ''
        if series is not None and series != '':
            osystem, release = find_osystem_and_release_from_release_name(
                series)
            if osystem is not None:
                key_required = get_release_requires_key(release)
                self.data['osystem'] = osystem['name']
                self.data['distro_series'] = '%s/%s%s' % (
                    osystem['name'],
                    series,
                    key_required,
                    )
            else:
                self.data['distro_series'] = series

    def set_license_key(self, license_key=''):
        """Sets the license key."""
        self.is_bound = True
        self.data['license_key'] = license_key

    def set_hwe_kernel(self, hwe_kernel=''):
        """Sets the hwe_kernel."""
        self.is_bound = True
        self.data['hwe_kernel'] = hwe_kernel

    hostname = forms.CharField(
        label="Host name", required=False, help_text=(
            "The FQDN (Fully Qualified Domain Name) is derived from the "
            "host name: If the cluster controller for this node is managing "
            "DNS then the domain part in the host name (if any) is replaced "
            "by the domain defined on the cluster; if the cluster controller "
            "does not manage DNS, then the host name as entered will be the "
            "FQDN."))

    swap_size = forms.CharField(
        label="Swap size", required=False, help_text=(
            "The size of the swap file in bytes. The field also accepts K, M, "
            "G and T meaning kilobytes, megabytes, gigabytes and terabytes."))

    boot_type = forms.ChoiceField(
        choices=NODE_BOOT_CHOICES, initial=NODE_BOOT.FASTPATH, required=False)

    class Meta:
        model = Node

        # Fields that the form should generate automatically from the
        # model:
        # Note: fields have to be added here even if they were defined manually
        # elsewhere in the form
        fields = (
            'hostname',
            'architecture',
            'osystem',
            'distro_series',
            'license_key',
            'disable_ipv4',
            'swap_size',
            'boot_type',
            'min_hwe_kernel',
            'hwe_kernel'
            )


class DeviceForm(MAASModelForm):
    parent = forms.ModelChoiceField(
        required=False, initial=None,
        queryset=Node.objects.all(), to_field_name='system_id')

    class Meta:
        model = Device

        fields = (
            'hostname',
            'parent',
        )

    def __init__(self, request=None, *args, **kwargs):
        super(DeviceForm, self).__init__(*args, **kwargs)
        self.request = request

        instance = kwargs.get('instance')
        # Are we creating a new device object?
        self.new_device = (instance is None)
        self.set_up_initial_device(instance)

    def set_up_initial_device(self, instance):
        """Initialize the 'parent' field if a device instance was given.

        This is a workaround for Django bug #17657.
        """
        if instance is not None and instance.parent is not None:
            self.initial['parent'] = instance.parent.system_id

    def save(self, commit=True):
        device = super(DeviceForm, self).save(commit=False)
        device.installable = False
        if self.new_device:
            # Set the owner: devices are owned by their creator.
            device.owner = self.request.user
            device.nodegroup = NodeGroup.objects.ensure_master()
        device.save()
        return device

CLUSTER_NOT_AVAILABLE = mark_safe(
    "The cluster controller for this node is not responding; power type "
    "validation is not available."
)


NO_ARCHITECTURES_AVAILABLE = mark_safe(
    "No architectures are available to use for this node; boot images may not "
    "have been imported on the selected cluster controller, or it may be "
    "unavailable."
)


class AdminNodeForm(NodeForm):
    """A `NodeForm` which includes fields that only an admin may change."""

    zone = forms.ModelChoiceField(
        label="Physical zone", required=False,
        initial=Zone.objects.get_default_zone,
        queryset=Zone.objects.all(), to_field_name='name')

    cpu_count = forms.IntegerField(
        required=False, initial=0, label="CPU Count")
    memory = forms.IntegerField(
        required=False, initial=0, label="Memory (MiB)")

    class Meta:
        model = Node

        # Fields that the form should generate automatically from the
        # model:
        fields = NodeForm.Meta.fields + (
            'power_type',
            'power_parameters',
            'cpu_count',
            'memory',
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
                set_form_error(
                    self, "power_type", CLUSTER_NOT_AVAILABLE + e.args[0])
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


class MACAddressForm(MAASModelForm):
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


class KeyForm(MAASModelForm):
    """Base class for `SSHKeyForm` and `SSLKeyForm`."""

    def __init__(self, user, *args, **kwargs):
        super(KeyForm, self).__init__(*args, **kwargs)
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


class SSHKeyForm(KeyForm):
    key = forms.CharField(
        label="Public key",
        widget=forms.Textarea(attrs={'rows': '5', 'cols': '30'}),
        required=True)

    class Meta:
        model = SSHKey


class SSLKeyForm(KeyForm):
    key = forms.CharField(
        label="SSL key",
        widget=forms.Textarea(attrs={'rows': '15', 'cols': '30'}),
        required=True)

    class Meta:
        model = SSLKey


class MultipleMACAddressField(forms.MultiValueField):

    def __init__(self, nb_macs=1, *args, **kwargs):
        fields = [MACAddressFormField() for _ in range(nb_macs)]
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

MAX_MESSAGES = 10


def merge_error_messages(summary, errors, limit=MAX_MESSAGES):
    """Merge a collection of errors into a summary message of limited size.

    :param summary: The message summarizing the error.
    :type summary: unicode
    :param errors: The list of errors to merge.
    :type errors: iterable
    :param limit: The maximum number of individual error messages to include in
        the summary error message.
    :type limit: int
    """
    ellipsis_msg = ''
    if len(errors) > limit:
        nb_errors = len(errors) - limit
        ellipsis_msg = (
            " and %d more error%s" % (
                nb_errors,
                's' if nb_errors > 1 else ''))
    return "%s (%s%s)" % (
        summary,
        ' \u2014 '.join(errors[:limit]),
        ellipsis_msg
    )


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
            self.errors['mac_addresses'] = [merge_error_messages(
                "One or more MAC addresses is invalid.",
                self.errors['mac_addresses'])]
        return valid

    def clean_mac_addresses(self):
        data = self.cleaned_data['mac_addresses']
        errors = []
        if self.instance.id is not None:
            # This node is already in the system. We should consider adding
            # MACAddresses that are already attached to this node a valid
            # operation.
            for mac in data:
                mac_on_other_nodes = MACAddress.objects.filter(
                    mac_address=mac.lower()).exclude(node=self.instance)
                if mac_on_other_nodes:
                    errors.append(
                        'MAC address %s already in use on %s.' %
                        (mac, mac_on_other_nodes[0].node.hostname))
        else:
            # This node does not exist yet, we should only check if this
            # MACAddress is already attached to another node.
            for mac in data:
                if MACAddress.objects.filter(mac_address=mac.lower()).exists():
                    errors.append(
                        'MAC address %s already in use on %s.' %
                        (mac, MACAddress.objects.filter(
                            mac_address=mac.lower()).first().node.hostname))
        if errors:
            raise ValidationError({'mac_addresses': errors})
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


class DeviceWithMACsForm(WithMACAddressesMixin, DeviceForm):
    """A version of the DeviceForm which includes the multi-MAC address field.
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
            (action.name, action.display)
            for action in ACTION_CLASSES])

    # The name of the input button used with this form.
    input_name = 'action'

    def __init__(self, instance, *args, **kwargs):
        super(NodeActionForm, self).__init__(*args, **kwargs)
        self.node = instance
        self.actions = compile_node_actions(instance, self.user, self.request)
        self.action_buttons = self.actions.values()

    def display_message(self, message, msg_level=messages.INFO):
        """Show `message` as feedback after performing an action."""
        if self.request is not None:
            messages.add_message(self.request, msg_level, message)

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

    def save(self):
        """An action was requested.  Perform it.

        This implementation of `save` does not support the `commit` argument.
        """
        action_name = self.data.get('action')
        action = self.actions.get(action_name)
        msg_level = messages.INFO
        try:
            message = action.execute()
        except NodeActionError as e:
            message = e.message
            msg_level = messages.ERROR
        self.display_message(message, msg_level)
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


class ProfileForm(MAASModelForm):
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
    # List of fields that should be considered configuration fields.
    # Consider all the fields as configuration fields if this is None.
    config_fields = None

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
            consider_field = (
                self.config_fields is None or
                config_name in self.config_fields
            )
            if consider_field:
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
                consider_field = (
                    self.config_fields is None or
                    name in self.config_fields
                )
                if consider_field:
                    Config.objects.set_config(name, value)
            return True


class MAASAndNetworkForm(ConfigForm):
    """Settings page, MAAS and Network section."""
    maas_name = get_config_field('maas_name')
    http_proxy = get_config_field('http_proxy')
    upstream_dns = get_config_field('upstream_dns')
    dnssec_validation = get_config_field('dnssec_validation')
    ntp_server = get_config_field('ntp_server')


class ThirdPartyDriversForm(ConfigForm):
    """Settings page, Third Party Drivers section."""
    enable_third_party_drivers = get_config_field('enable_third_party_drivers')


class StorageSettingsForm(ConfigForm):
    """Settings page, storage section."""
    default_storage_layout = get_config_field('default_storage_layout')
    enable_disk_erasing_on_release = get_config_field(
        'enable_disk_erasing_on_release')


class CommissioningForm(ConfigForm):
    """Settings page, Commissioning section."""

    def __init__(self, *args, **kwargs):
        # Skip ConfigForm.__init__ because we need the form intialized but
        # don't want _load_initial called until the field has been added.
        Form.__init__(self, *args, **kwargs)
        self.fields['commissioning_distro_series'] = get_config_field(
            'commissioning_distro_series')
        self._load_initials()


class DeployForm(ConfigForm):
    """Settings page, Deploy section."""

    def __init__(self, *args, **kwargs):
        # Skip ConfigForm.__init__ because we need the form intialized but
        # don't want _load_initial called until the field has been added.
        Form.__init__(self, *args, **kwargs)
        self.fields['default_osystem'] = get_config_field('default_osystem')
        self.fields['default_distro_series'] = (
            self._get_default_distro_series_field_for_ui())
        self._load_initials()

    def _get_default_distro_series_field_for_ui(self):
        """This create the field with os/release. This is needed by the UI
        to filter the releases based on the OS selection. The API uses the
        field defined in forms_settings.py"""
        usable_oses = list_all_usable_osystems()
        release_choices = list_release_choices(
            list_all_usable_releases(usable_oses), include_default=False)
        if len(release_choices) == 0:
            release_choices = [('---', '--- No Usable Release ---')]
        field = forms.ChoiceField(
            initial=Config.objects.get_config('default_distro_series'),
            choices=release_choices,
            validators=[validate_missing_boot_images],
            error_messages={
                'invalid_choice': compose_invalid_choice_text(
                    'release', release_choices)
            },
            label="Default OS release used for deployment",
            required=False)
        return field

    def _load_initials(self):
        super(DeployForm, self)._load_initials()
        initial_os = self.fields['default_osystem'].initial
        initial_series = self.fields['default_distro_series'].initial
        self.initial['default_distro_series'] = '%s/%s' % (
            initial_os,
            initial_series
            )

    def clean_default_distro_series(self):
        return clean_distro_series_field(
            self, 'default_distro_series', 'default_osystem')


class UbuntuForm(ConfigForm):
    """Settings page, Ubuntu section."""
    main_archive = get_config_field('main_archive')
    ports_archive = get_config_field('ports_archive')


class WindowsForm(ConfigForm):
    """Settings page, Windows section."""
    windows_kms_host = get_config_field('windows_kms_host')


class GlobalKernelOptsForm(ConfigForm):
    """Settings page, Global Kernel Parameters section."""
    kernel_opts = get_config_field('kernel_opts')


class BootSourceSettingsForm(ConfigForm):
    """Settings page, Boot Images section."""
    config_fields = ['boot_images_auto_import']

    boot_images_auto_import = get_config_field('boot_images_auto_import')
    boot_source_url = forms.CharField(
        label="Sync URL", required=True,
        help_text=(
            "URL to sync boot image from. E.g. "
            "http://maas.ubuntu.com/images/ephemeral-v2/releases/"))

    def __init__(self, *args, **kwargs):
        super(BootSourceSettingsForm, self).__init__(*args, **kwargs)
        self.configure_keyring_filename()
        self.load_initials()

    def configure_keyring_filename(self):
        """Create the keyring field if the boot source is not using
        keyring_data."""
        boot_source = BootSource.objects.first()
        if boot_source is None or len(boot_source.keyring_data) == 0:
            self.fields['boot_source_keyring'] = forms.CharField(
                label="Keyring Path", required=True,
                help_text=(
                    "Path to the keyring to validate the sync URL. E.g. "
                    "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"))

    def load_initials(self):
        """Load the initial values for the fields."""
        boot_source = BootSource.objects.first()
        if boot_source is None:
            return
        self.initial['boot_source_url'] = boot_source.url
        self.initial['boot_source_keyring'] = boot_source.keyring_filename

    def save(self):
        """Save the content of the fields into the database.

        This implementation of `save` does not support the `commit` argument.

        :return: Whether or not the content of the fields was valid and hence
            sucessfully saved into the detabase.
        :rtype: boolean
        """
        super(BootSourceSettingsForm, self).save()
        if self._errors:
            return False
        boot_source = BootSource.objects.first()
        if boot_source is None:
            boot_source = BootSource.objects.create(
                url=self.cleaned_data['boot_source_url'],
                keyring_filename=self.cleaned_data['boot_source_keyring'])
            return True
        boot_source.url = self.cleaned_data['boot_source_url']
        if 'boot_source_keyring' in self.cleaned_data:
            boot_source.keyring_filename = (
                self.cleaned_data['boot_source_keyring'])
        boot_source.save()
        return True


ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE = (
    "New static IP range does not include already-allocated IP "
    "addresses.")


ERROR_MESSAGE_STATIC_RANGE_IN_USE = (
    "Cannot remove static IP range when there are allocated IP addresses "
    "in that range.")


ERROR_MESSAGE_DYNAMIC_RANGE_SPANS_SLASH_16S = (
    "All addresses in the dynamic range must be within the same /16 "
    "network.")

ERROR_MESSAGE_INVALID_RANGE = (
    "Invalid IP range (high IP address must not be less than low IP address).")


def validate_new_dynamic_range_size(instance, ip_range_low, ip_range_high):
    """Check that a ip address range is of a manageable size.

    :raises ValidationError: If the ip range is larger than a /16
        IPv4 network.
    """
    # Return early if the instance is not already managed, its dynamic
    # IP range hasn't changed, or the new values are blank.
    if not instance.is_managed:
        return True
    # Deliberately vague check to allow for empty strings.
    if not ip_range_low and not ip_range_high:
        return True
    if (ip_range_low == instance.ip_range_low and
       ip_range_high == instance.ip_range_high):
        return True

    try:
        ip_range = IPRange(ip_range_low, ip_range_high)
    except AddrFormatError:
        raise ValidationError(ERROR_MESSAGE_INVALID_RANGE)

    # Allow any size of dynamic range for v6 networks, but limit v4
    # networks to /16s.
    if ip_range.version == 6:
        return True

    slash_16_network = IPNetwork("%s/16" % IPAddress(ip_range.first))
    if not ip_range_within_network(ip_range, slash_16_network):
        raise ValidationError(ERROR_MESSAGE_DYNAMIC_RANGE_SPANS_SLASH_16S)


def validate_new_static_ip_ranges(instance, static_ip_range_low,
                                  static_ip_range_high):
    """Check that new static IP ranges don't exclude allocated addresses.

    If there are IP addresses allocated within a `NodeGroupInterface`'s
    existing static IP range which would fall outside of the new range,
    raise a ValidationError.
    """
    # Return early if the instance is not already managed, it currently
    # has no static IP range, or the static IP range hasn't changed.
    if not instance.is_managed:
        return True
    # Deliberately vague check to allow for empty strings.
    if (not instance.static_ip_range_low or
       not instance.static_ip_range_high):
        return True
    if (static_ip_range_low == instance.static_ip_range_low and
       static_ip_range_high == instance.static_ip_range_high):
        return True

    cursor = connection.cursor()

    # Deliberately vague check to allow for empty strings.
    if static_ip_range_low or static_ip_range_high:
        # Find any allocated addresses within the old static range which do
        # not fall within the *new* static range. This means that we allow
        # for range expansion and contraction *unless* that means dropping
        # IP addresses that are already allocated.
        cursor.execute("""
            SELECT TRUE FROM maasserver_staticipaddress
                WHERE  ip >= %s AND ip <= %s
                    AND (ip < %s OR ip > %s)
            """, (
            instance.static_ip_range_low,
            instance.static_ip_range_high,
            static_ip_range_low,
            static_ip_range_high))
        results = cursor.fetchall()
        if any(results):
            raise forms.ValidationError(
                ERROR_MESSAGE_STATIC_IPS_OUTSIDE_RANGE)
    else:
        # Check that there's no IP addresses allocated in the old range;
        # if there are, we can't remove the range yet.
        cursor.execute("""
            SELECT TRUE FROM maasserver_staticipaddress
                WHERE ip >= %s AND ip <= %s
            """, (
            instance.static_ip_range_low,
            instance.static_ip_range_high))
        results = cursor.fetchall()
        if any(results):
            raise forms.ValidationError(
                ERROR_MESSAGE_STATIC_RANGE_IN_USE)
    return True


def create_Network_from_NodeGroupInterface(interface):
    """Given a `NodeGroupInterface`, create its Network counterpart."""
    if not interface.subnet:
        return

    name, vlan_tag = get_name_and_vlan_from_cluster_interface(
        interface.nodegroup.name, interface.interface)
    ipnetwork = _make_network_from_subnet(interface.ip, interface.subnet)
    network = Network(
        name=name,
        ip=unicode(ipnetwork.network),
        netmask=unicode(ipnetwork.netmask),
        default_gateway=interface.router_ip,
        vlan_tag=vlan_tag,
        description=(
            "Auto created when creating interface %s on cluster "
            "%s" % (interface.name, interface.nodegroup.name)),
        )
    try:
        network.save()
    except (IntegrityError, ValidationError) as e:
        # It probably already exists, keep calm and carry on.
        maaslog.warning(
            "Failed to create Network when adding/editing cluster "
            "interface %s with error [%s]. This is OK if it already "
            "exists." % (name, unicode(e)))
        return
    return network


def disambiguate_name(original_name, ip_address):
    """Return a unique variant of `original_name` for a cluster interface.

    This function has no knowledge of other existing cluster interfaces.  It
    disambiguates based purely on the given data and random numbers.

    :param original_name: The originally proposed name for the cluster
        interface, which presumably turned out to be ambiguous.
    :param ip_address: IP address for the cluster interface (either as a
        string or as an `IPAddress`).  Used to determine whether the interface
        is an IPv4 one or an IPv6 one.
    :return: A version of `original_name` with a disambiguating suffix.  The
        suffix contains both the IP version (`ipv4` or `ipv6`) and possibly a
        random part to avoid further clashes.
    """
    ip_version = IPAddress(ip_address).version
    assert ip_version in (4, 6)
    if ip_version == 6:
        # IPv6 cluster interface.  In principle there could be many of these
        # on the same network interface, so add a random suffix.
        suffix = 'ipv6-%d' % randint(10000, 99999)
    else:
        # IPv4 cluster interface.  There can be only one of these on the
        # network interface, so just suffixing '-ipv4' to the name should make
        # it unique.
        suffix = 'ipv4'
    return '%s-%s' % (original_name, suffix)


class NodeGroupInterfaceForm(MAASModelForm):

    management = forms.TypedChoiceField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, required=False,
        coerce=int, empty_value=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT,
        help_text=(
            "If you enable DHCP management, you will need to install the "
            "'maas-dhcp' package on this cluster controller.  Similarly, you "
            "will need to install the 'maas-dns' package on this region "
            "controller to be able to enable DNS management."
            ))

    # XXX mpontillo 2015-07-23: need a custom field for this, for IPv4/IPv6
    # address or prefix length.
    subnet_mask = forms.CharField(required=False)

    class Meta:
        model = NodeGroupInterface
        fields = (
            'name',
            'interface',
            'management',
            'ip',
            'router_ip',
            'subnet_mask',
            'ip_range_low',
            'ip_range_high',
            'static_ip_range_low',
            'static_ip_range_high',
            )

    def __init__(self, *args, **kwargs):
        super(NodeGroupInterfaceForm, self).__init__(*args, **kwargs)
        if not self.initial.get('subnet_mask'):
            self.initial['subnet_mask'] = self.get_subnet_mask()

    def save(self, *args, **kwargs):
        """Override `MAASModelForm`.save() so that the network data is copied
        to a `Network` instance."""
        # Note: full_clean() should not be needed here, but in some cases
        # it isn't being called before reaching this point. (Another form
        # also does this; the cause should be investigated.)
        self.full_clean()
        ip = self.cleaned_data.get('ip')
        subnet_mask = self.cleaned_data.get('subnet_mask')

        subnet = None
        if subnet_mask:
            cidr = create_cidr(ip, subnet_mask)
            subnet, _ = Subnet.objects.get_or_create(
                cidr=cidr, defaults={
                    'name': cidr,
                    'cidr': cidr,
                    'space': Space.objects.get_default_space()
                })

        interface = super(NodeGroupInterfaceForm, self).save(*args, **kwargs)
        interface.subnet = subnet
        interface.save()

        if interface.network is None:
            return interface
        create_Network_from_NodeGroupInterface(interface)
        return interface

    def compute_name(self):
        """Return the value the `name` field should have.

        A cluster interface's name defaults to the name of its network
        interface, unless that name is already taken, in which case it gets
        a disambiguating suffix.
        """
        name = self.cleaned_data.get('name')
        # Deliberately vague test: an unset name can be None or empty.
        if name:
            # Name is set.  Done.
            return name
        if self.instance.name:
            # No name given, but instance already had one.  Keep it.
            return self.instance.name

        # No name yet.  Pick a default.  Use the interface name for
        # compatibility with clients that expect the pre-1.6 behaviour, where
        # the 'name' and 'interface' fields were the same thing.
        interface = self.cleaned_data.get('interface')
        name = make_name_from_interface(interface)
        # Get the cluster to which this interface is attached.  There may not
        # be one, since it may be a placeholder instance that is still being
        # initialised by the same request that is also creating the interface.
        # In that case, self.instance.nodegroup will not be None, but rather
        # an ORM stub which crashes when accessed.
        cluster = get_one(
            NodeGroup.objects.filter(id=self.instance.nodegroup_id))
        if cluster is not None and interface:
            siblings = cluster.nodegroupinterface_set
            if siblings.filter(name=name).exists():
                # This name is already in use.  Add a suffix to make it unique.
                return disambiguate_name(name, self.cleaned_data['ip'])

        return name

    def get_duplicate_fqdns(self):
        """Get duplicate FQDNs created by using the new management setting."""
        # We need to know if the new fqdn of any of the nodes in this
        # cluster will conflict with the new FQDN of other nodes in this
        # cluster.
        cluster_nodes = Node.objects.filter(nodegroup=self.instance.nodegroup)
        fqdns = [
            nodegroup_fqdn(node.hostname, self.instance.nodegroup.name)
            for node in cluster_nodes]
        duplicates = [fqdn for fqdn in fqdns if fqdns.count(fqdn) > 1]

        # We also don't want FQDN conflicts with nodes in other clusters.
        nodes_and_fqdns = zip(cluster_nodes, fqdns)
        other_cluster_duplicates = [
            fqdn for node, fqdn in nodes_and_fqdns
            if fqdn_is_duplicate(node, fqdn)]
        duplicates.extend(other_cluster_duplicates)

        return set(duplicates)

    def clean_management(self):
        management = self.cleaned_data['management']

        # When the interface doesn't manage DNS, we don't need to worry
        # about creating duplicate FQDNs, because we're covered by hostname
        # uniqueness.
        if management != NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS:
            return management

        # The NodeGroupInterface instance doesn't always have a
        # nodegroup defined for it when we validate. For instance, when
        # a NodeGroupDefineForm is used, NodeGroupInterfaceForms are
        # validated prior to the NodeGroup being created.
        if not hasattr(self.instance, "nodegroup"):
            return management

        duplicates = self.get_duplicate_fqdns()

        if len(duplicates) > 0:
            raise ValidationError(
                "Enabling DNS management creates duplicate FQDN(s): %s." % (
                    ", ".join(set(duplicates))))

        return management

    def clean(self):
        cleaned_data = super(NodeGroupInterfaceForm, self).clean()
        cleaned_data['name'] = self.compute_name()
        self.clean_dependant_subnet_mask(cleaned_data)
        self.clean_dependant_ip_ranges(cleaned_data)
        self.clean_ip_range_bounds(cleaned_data)
        self.clean_dependant_ips_in_network(cleaned_data)
        return cleaned_data

    def get_subnet_mask(self, cleaned_data=None):
        # `subnet_mask` is not among the form's fields and thus its
        # initial value isn't populated from the related ngi instance
        # by BaseModelForm.__init__.
        subnet_mask = None
        if cleaned_data is not None:
            subnet_mask = cleaned_data.get('subnet_mask')
        if not subnet_mask:
            subnet_mask = self.data.get('subnet_mask')
        if not subnet_mask:
            if self.instance is not None:
                return self.instance.subnet_mask
            else:
                return ''
        else:
            return subnet_mask

    def clean_dependant_subnet_mask(self, cleaned_data):
        ip_addr = cleaned_data.get('ip')
        if ip_addr and IPAddress(ip_addr).version == 6:
            netmask = cleaned_data.get('subnet_mask')
            if netmask in (None, ''):
                netmask = 'ffff:ffff:ffff:ffff::'
            cleaned_data['subnet_mask'] = unicode(netmask)
        new_management = cleaned_data.get('management')
        new_subnet_mask = self.get_subnet_mask(cleaned_data)
        required_subnet_mask = (
            new_management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED and
            not new_subnet_mask)
        if required_subnet_mask:
            set_form_error(
                self, 'subnet_mask',
                "That field cannot be empty (unless that interface is "
                "'unmanaged')")

    def get_network(self, cleaned_data):
        subnet_mask = self.get_subnet_mask(cleaned_data)
        ip = cleaned_data.get('ip')
        if subnet_mask and ip:
            return IPNetwork(unicode(ip) + '/' + unicode(subnet_mask))
        else:
            return None

    def clean_dependant_ips_in_network(self, cleaned_data):
        """Ensure that the network settings are all congruent.

        Specifically, it ensures that the router address, the DHCP address
        range, and the broadcast address if given, all fall within the network
        defined by the interface's IP address and the subnet mask.

        If no broadcast address is given, the network's default broadcast
        address will be used.
        """
        network = self.get_network(cleaned_data)
        if network is None:
            return
        fields_in_network = [
            "router_ip",
            "ip_range_low",
            "ip_range_high",
            "static_ip_range_low",
            "static_ip_range_high",
        ]
        for field in fields_in_network:
            ip = cleaned_data.get(field)
            if ip and IPAddress(ip) not in network:
                msg = "%s not in the %s network" % (ip, unicode(network.cidr))
                set_form_error(self, field, msg)

    def clean_dependant_ip_ranges(self, cleaned_data):
        dynamic_range_low = cleaned_data.get('ip_range_low')
        dynamic_range_high = cleaned_data.get('ip_range_high')
        try:
            validate_new_dynamic_range_size(
                self.instance, dynamic_range_low, dynamic_range_high)
        except forms.ValidationError as exception:
            set_form_error(self, 'ip_range_low', exception.message)
            set_form_error(self, 'ip_range_high', exception.message)

        static_ip_range_low = cleaned_data.get('static_ip_range_low')
        static_ip_range_high = cleaned_data.get('static_ip_range_high')
        try:
            validate_new_static_ip_ranges(
                self.instance, static_ip_range_low, static_ip_range_high)
        except forms.ValidationError as exception:
            set_form_error(self, 'static_ip_range_low', exception.message)
            set_form_error(self, 'static_ip_range_high', exception.message)
        return cleaned_data

    def manages_static_range(self, cleaned_data):
        """Is this a managed interface with a static IP range configured?"""
        is_managed = cleaned_data.get('is_managed', False)
        static_ip_range_low = cleaned_data.get('static_ip_range_low', None)
        static_ip_range_high = cleaned_data.get('static_ip_range_high', None)
        # Deliberately vague implicit conversion to bool: a blank IP address
        # can show up internally as either None or an empty string.
        return is_managed and static_ip_range_low and static_ip_range_high

    def clean_ip_range_bounds(self, cleaned_data):
        """Ensure that the static and dynamic ranges have sane bounds."""
        if not self.manages_static_range(cleaned_data):
            # Exit early with nothing to do.
            return cleaned_data

        ip_range_low = cleaned_data.get('ip_range_low', "")
        ip_range_high = cleaned_data.get('ip_range_high', "")
        static_ip_range_low = cleaned_data.get('static_ip_range_low', "")
        static_ip_range_high = cleaned_data.get('static_ip_range_high', "")

        ip_range_low = IPAddress(ip_range_low)
        ip_range_high = IPAddress(ip_range_high)
        static_ip_range_low = IPAddress(static_ip_range_low)
        static_ip_range_high = IPAddress(static_ip_range_high)

        message_base = (
            "Lower bound %s is higher than upper bound %s")
        try:
            IPRange(static_ip_range_low, static_ip_range_high)
        except AddrFormatError:
            message = (
                message_base % (
                    static_ip_range_low, static_ip_range_high))
            set_form_error(self, 'static_ip_range_low', message)
            set_form_error(self, 'static_ip_range_high', message)
        try:
            IPRange(ip_range_low, ip_range_high)
        except AddrFormatError:
            message = (
                message_base % (self.ip_range_low, self.ip_range_high))
            set_form_error(self, 'ip_range_low', message)
            set_form_error(self, 'ip_range_high', message)

        return cleaned_data

INTERFACES_VALIDATION_ERROR_MESSAGE = (
    "Invalid json value: should be a list of dictionaries, each containing "
    "the information needed to initialize an interface.")


# The DNS zone name used for nodegroups when none is explicitly provided.
DEFAULT_DNS_ZONE_NAME = 'maas'


def validate_nodegroupinterfaces_json(interfaces):
    """Check `NodeGroupInterface` definitions as found in a requst.

    This validates that the `NodeGroupInterface` definitions found in a
    request to `NodeGroupDefineForm` conforms to the expected basic structure:
    a list of dicts.

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


class NodeGroupDefineForm(MAASModelForm):
    """Define a `NodeGroup`, along with its interfaces.

    This form can create a new `NodeGroup`, or in the case where a cluster
    automatically becomes the master, updating an existing one.
    """

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
        super(NodeGroupDefineForm, self).__init__(*args, **kwargs)
        self.status = status

    def clean_name(self):
        data = self.cleaned_data['name']
        if data == '':
            return DEFAULT_DNS_ZONE_NAME
        else:
            return data

    def clean(self):
        cleaned_data = super(NodeGroupDefineForm, self).clean()
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

    def save(self, **kwargs):
        nodegroup = super(NodeGroupDefineForm, self).save()
        # Go through the interface definitions, but process the IPv4 ones
        # first.  This way, if the NodeGroupInterfaceForm needs to make up
        # unique names for cluster interfaces on the same network interface,
        # the IPv4 one will get first stab at getting the exact same name as
        # the network interface.
        interfaces = sorted(
            self.cleaned_data['interfaces'],
            key=lambda definition: IPAddress(definition['ip']).version)
        for interface in interfaces:
            instance = NodeGroupInterface(nodegroup=nodegroup)
            form = NodeGroupInterfaceForm(data=interface, instance=instance)
            form.save()
        if self.status is not None:
            nodegroup.status = self.status
            nodegroup.save()
        return nodegroup


class NodeGroupEdit(MAASModelForm):

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
            'default_disable_ipv4',
            )

    def __init__(self, *args, **kwargs):
        super(NodeGroupEdit, self).__init__(*args, **kwargs)
        # Hide the default_disable_ipv4 field if the cluster is not
        # configured for IPv6.
        show_default_disable_ipv4 = contains_managed_ipv6_interface(
            self.instance.nodegroupinterface_set.all())
        if not show_default_disable_ipv4:
            self.fields['default_disable_ipv4'] = forms.BooleanField(
                label="", required=False, widget=forms.HiddenInput())

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

    def clean_default_disable_ipv4(self):
        data = self.submitted_data
        if 'ui_submission' in data and 'default_disable_ipv4' not in data:
            # In the UI, where all fields are submitted except checkboxes in
            # the "off" state, a missing boolean field means False.
            # (In the API, as enforced by MAASModelForm, a missing boolean
            # field means "unchanged").
            self.cleaned_data['default_disable_ipv4'] = False
        return self.cleaned_data['default_disable_ipv4']


class TagForm(MAASModelForm):

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
    display = "Set physical zone"


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
            [('', 'Select Action')] +
            [(action.name, action.display) for action in ACTION_CLASSES]
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
                (SetZoneBulkAction.name, SetZoneBulkAction.display))
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

    @transactional
    def _perform_action_on_node(self, system_id, action_class):
        """Perform a node action on the identified node.

        This is *transactional*, meaning it will commit its changes on
        success, and roll-back if not.

        Returns a string describing what was done, one of:

        * not_actionable
        * not_permitted
        * done

        :param system_id: A `Node.system_id` value.
        :param action_class: A value from `ACTIONS_DICT`.
        """
        node = Node.objects.get(system_id=system_id)
        if node.status in action_class.actionable_statuses:
            action_instance = action_class(node=node, user=self.user)
            if action_instance.inhibit() is not None:
                return "not_actionable"
            else:
                if action_instance.is_permitted():
                    # Do not let execute() raise a redirect exception
                    # because this action is part of a bulk operation.
                    try:
                        action_instance.execute()
                    except NodeActionError:
                        return "not_actionable"
                    else:
                        return "done"
                else:
                    return "not_permitted"
        else:
            return "not_actionable"

    @asynchronous(timeout=FOREVER)
    def _perform_action_on_nodes(
            self, system_ids, action_class, concurrency=2):
        """Perform a node action on the identified nodes.

        This is *asynchronous*.

        :param system_ids: An iterable of `Node.system_id` values.
        :param action_class: A value from `ACTIONS_DICT`.
        :param concurrency: The number of actions to run concurrently.

        :return: A `dict` mapping `system_id` to results, where the result can
            be a string (see `_perform_action_on_node`), or a `Failure` if
            something went wrong.
        """
        # We're going to be making the same call for every specified node, so
        # bundle up the common bits here to keep the noise down later on.
        perform = partial(
            deferToThread, self._perform_action_on_node,
            action_class=action_class)

        # The results will be a `system_id` -> `result` mapping, where
        # `result` can be a string like "done" or "not_actionable", or a
        # Failure instance.
        results = {}

        # Convenient callback.
        def record(result, system_id):
            results[system_id] = result

        # A *lazy* list of tasks to be run. It's very important that each task
        # is only created at the moment it's needed. Each task records its
        # outcome via `record`, be that success or failure.
        tasks = (
            perform(system_id).addBoth(record, system_id)
            for system_id in system_ids
        )

        # Create `concurrency` co-iterators. Each draws work from `tasks`.
        deferreds = (coiterate(tasks) for _ in xrange(concurrency))
        # Capture the moment when all the co-iterators have finished.
        done = DeferredList(deferreds, consumeErrors=True)
        # Return only the `results` mapping; ignore the result from `done`.

        return done.addCallback(lambda _: results)

    def perform_action(self, action_name, system_ids):
        """Perform a node action on the identified nodes.

        :param action_name: Name of a node action in `ACTIONS_DICT`.
        :param system_ids: Iterable of `Node.system_id` values.
        :return: A tuple as returned by `save`.
        """
        action_class = ACTIONS_DICT.get(action_name)
        results = self._perform_action_on_nodes(system_ids, action_class)
        # There is a lot of valuable information in `results`, including
        # failures, but currently we're only interested in basic stats.
        stats = Counter(
            result for result in results.viewvalues()
            if not isinstance(result, Failure))
        return stats["done"], stats["not_actionable"], stats["not_permitted"]

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

        Currently, in the event of a NodeActionError this is thrown into the
        "not actionable" bucket in lieu of an overhaul of this form to
        properly report errors for part-failing actions.  In this case
        the transaction will still be valid for the actions that did complete
        successfully.
        """
        action_name = self.cleaned_data['action']
        system_ids = self.cleaned_data['system_id']
        if action_name == SetZoneBulkAction.name:
            return self.set_zone(system_ids)
        else:
            return self.perform_action(action_name, system_ids)


class DownloadProgressForm(MAASModelForm):
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


class ZoneForm(MAASModelForm):

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


class NetworkForm(MAASModelForm):

    class Meta:
        model = Network
        fields = (
            'name',
            'description',
            'ip',
            'netmask',
            'vlan_tag',
            'default_gateway',
            'dns_servers',
            )

    mac_addresses = NodeMACAddressChoiceField(
        label="Connected network interface cards",
        queryset=MACAddress.objects.all().order_by(
            'node__hostname', 'mac_address'),
        required=False,
        to_field_name='mac_address',
        widget=forms.SelectMultiple(attrs={'size': 10}),
        )

    def __init__(self, data=None, instance=None,
                 delete_macs_if_not_present=True, **kwargs):
        """
        :param data: The web request.data
        :param instance: the Network instance
        :param delete_macs_if_not_present: If there's no mac_addresses present
            in the data, then assume that the caller wants to delete them.
            Override with True if you don't want that to happen. Yes, this
            is a horrible kludge so the same form works in the API and the
            web view.
        """
        super(NetworkForm, self).__init__(
            data=data, instance=instance, **kwargs)
        self.macs_in_request = data.get("mac_addresses") if data else None
        self.set_up_initial_macaddresses(instance)
        self.delete_macs_if_not_present = delete_macs_if_not_present

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
        # Because the form is used in the web view AND the API we need a
        # hack. The API uses separate ops to amend the mac_addresses
        # list, however the web UI does not. To preserve the API
        # behaviour, its handler passes delete_macs_if_not_present as False.
        if self.delete_macs_if_not_present and self.macs_in_request is None:
            network.macaddress_set.clear()
        elif macaddresses is not None:
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


class BootSourceForm(MAASModelForm):
    """Form for the Boot Source API."""

    class Meta:
        model = BootSource
        fields = (
            'url',
            'keyring_filename',
            'keyring_data',
            )

    keyring_filename = forms.CharField(
        label="The path to the keyring file for this BootSource.",
        required=False)

    keyring_data = forms.FileField(
        label="The GPG keyring for this BootSource, as a binary blob.",
        required=False)

    def __init__(self, **kwargs):
        super(BootSourceForm, self).__init__(**kwargs)

    def clean_keyring_data(self):
        """Process 'keyring_data' field.

        Return the InMemoryUploadedFile's content so that it can be
        stored in the boot source's 'keyring_data' binary field.
        """
        data = self.cleaned_data.get('keyring_data', None)
        if data is not None:
            return data.read()
        return data


class BootSourceSelectionForm(MAASModelForm):
    """Form for the Boot Source Selection API."""

    class Meta:
        model = BootSourceSelection
        fields = (
            'os',
            'release',
            'arches',
            'subarches',
            'labels',
            )

    # Use UnconstrainedMultipleChoiceField fields for multiple-choices
    # fields instead of the default (djorm-ext-pgarray's ArrayFormField):
    # ArrayFormField deals with comma-separated lists and here we want to
    # handle multiple-values submissions.
    arches = UnconstrainedMultipleChoiceField(label="Architecture list")
    subarches = UnconstrainedMultipleChoiceField(label="Subarchitecture list")
    labels = UnconstrainedMultipleChoiceField(label="Label list")

    def __init__(self, boot_source=None, **kwargs):
        super(BootSourceSelectionForm, self).__init__(**kwargs)
        if 'instance' in kwargs:
            self.boot_source = kwargs['instance'].boot_source
        else:
            self.boot_source = boot_source

    def clean(self):
        cleaned_data = super(BootSourceSelectionForm, self).clean()

        # Don't filter on OS if not provided. This is to maintain
        # backwards compatibility for when OS didn't exist in the API.
        if cleaned_data['os']:
            cache = BootSourceCache.objects.filter(
                boot_source=self.boot_source, os=cleaned_data['os'],
                release=cleaned_data['release'])
        else:
            cache = BootSourceCache.objects.filter(
                boot_source=self.boot_source, release=cleaned_data['release'])

        if not cache.exists():
            set_form_error(
                self, "os",
                "OS %s with release %s has no available images for download" %
                (cleaned_data['os'], cleaned_data['release']))
            return cleaned_data

        values = cache.values_list("arch", "subarch", "label")
        arches, subarches, labels = zip(*values)

        # Validate architectures.
        required_arches_set = set(arch for arch in cleaned_data['arches'])
        wildcard_arches = '*' in required_arches_set
        if not wildcard_arches and not required_arches_set <= set(arches):
            set_form_error(
                self, "arches",
                "No available images to download for %s" %
                cleaned_data['arches'])

        # Validate subarchitectures.
        required_subarches_set = set(sa for sa in cleaned_data['subarches'])
        wildcard_subarches = '*' in required_subarches_set
        if (
            not wildcard_subarches and
            not required_subarches_set <= set(subarches)
                ):
            set_form_error(
                self, "subarches",
                "No available images to download for %s" %
                cleaned_data['subarches'])

        # Validate labels.
        required_labels_set = set(label for label in cleaned_data['labels'])
        wildcard_labels = '*' in required_labels_set
        if not wildcard_labels and not required_labels_set <= set(labels):
            set_form_error(
                self, "labels",
                "No available images to download for %s" %
                cleaned_data['labels'])

        return cleaned_data

    def save(self, *args, **kwargs):
        boot_source_selection = super(
            BootSourceSelectionForm, self).save(commit=False)
        boot_source_selection.boot_source = self.boot_source
        if kwargs.get('commit', True):
            boot_source_selection.save()
        return boot_source_selection


class LicenseKeyForm(MAASModelForm):
    """Form for global license keys."""

    class Meta:
        model = LicenseKey
        fields = (
            'osystem',
            'distro_series',
            'license_key',
            )

    def __init__(self, *args, **kwargs):
        super(LicenseKeyForm, self).__init__(*args, **kwargs)
        self.set_up_osystem_and_distro_series_fields(kwargs.get('instance'))

    def set_up_osystem_and_distro_series_fields(self, instance):
        """Create the `osystem` and `distro_series` fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        usable operating systems and distro_series.
        """
        osystems = list_all_usable_osystems()
        releases = list_all_releases_requiring_keys(osystems)

        # Remove the operating systems that do not have any releases that
        # require license keys. Don't want them to show up in the UI or be
        # used in the API.
        osystems = [
            osystem
            for osystem in osystems
            if osystem['name'] in releases
            ]

        os_choices = list_osystem_choices(osystems, include_default=False)
        distro_choices = list_release_choices(
            releases, include_default=False, with_key_required=False)
        invalid_osystem_message = compose_invalid_choice_text(
            'osystem', os_choices)
        invalid_distro_series_message = compose_invalid_choice_text(
            'distro_series', distro_choices)
        self.fields['osystem'] = forms.ChoiceField(
            label="OS", choices=os_choices, required=True,
            error_messages={'invalid_choice': invalid_osystem_message})
        self.fields['distro_series'] = forms.ChoiceField(
            label="Release", choices=distro_choices, required=True,
            error_messages={
                'invalid_choice': invalid_distro_series_message})
        if instance is not None:
            initial_value = get_distro_series_initial(
                osystems, instance, with_key_required=False)
            if instance is not None:
                self.initial['distro_series'] = initial_value

    def full_clean(self):
        # When this form is used from the API, the distro_series field will
        # not be formatted correctly. This is to make it easy on the user, and
        # not have to call the api with distro_series=os/series. This occurs
        # in full_clean, so the value is correct before validation occurs on
        # the distro_series field.
        if 'distro_series' in self.data and 'osystem' in self.data:
            if '/' not in self.data['distro_series']:
                self.data['distro_series'] = '%s/%s' % (
                    self.data['osystem'],
                    self.data['distro_series'],
                    )
        super(LicenseKeyForm, self).full_clean()

    def clean(self):
        """Validate distro_series and osystem match, and license_key is valid
        for selected operating system and series."""
        # Get the clean_data, check that all of the fields we need are
        # present. If not then the form will error, so no reason to continue.
        cleaned_data = super(LicenseKeyForm, self).clean()
        required_fields = ['license_key', 'osystem', 'distro_series']
        for field in required_fields:
            if field not in cleaned_data:
                return cleaned_data
        cleaned_data['distro_series'] = self.clean_osystem_distro_series_field(
            cleaned_data)
        self.validate_license_key(cleaned_data)
        return cleaned_data

    def clean_osystem_distro_series_field(self, cleaned_data):
        """Validate that os/distro_series matches osystem, and update the
        distro_series field, to remove the leading os/."""
        cleaned_osystem = cleaned_data['osystem']
        cleaned_series = cleaned_data['distro_series']
        series_os, release = cleaned_series.split('/', 1)
        if series_os != cleaned_osystem:
            raise ValidationError(
                "%s in distro_series does not match with "
                "operating system %s" % (release, cleaned_osystem))
        return release

    def validate_license_key(self, cleaned_data):
        """Validates that the license key is valid."""
        cleaned_key = cleaned_data['license_key']
        cleaned_osystem = cleaned_data['osystem']
        cleaned_series = cleaned_data['distro_series']
        if not validate_license_key(
                cleaned_osystem, cleaned_series, cleaned_key):
            raise ValidationError("Invalid license key.")


BOOT_RESOURCE_FILE_TYPE_CHOICES_UPLOAD = (
    ('tgz', "Root Image (tar.gz)"),
    ('ddtgz', "Root Compressed DD (dd -> tar.gz)"),
    )


class BootResourceForm(MAASModelForm):
    """Form for uploading boot resources."""

    class Meta:
        model = BootResource
        fields = (
            'name',
            'title',
            'architecture',
            'filetype',
            'content',
            )

    title = forms.CharField(label="Title", required=False)

    filetype = forms.ChoiceField(
        label="Filetype",
        choices=BOOT_RESOURCE_FILE_TYPE_CHOICES_UPLOAD,
        required=True, initial='tgz')

    content = forms.FileField(
        label="File", allow_empty_file=False)

    def __init__(self, *args, **kwargs):
        super(BootResourceForm, self).__init__(*args, **kwargs)
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

    def get_existing_resource(self, resource):
        """Return existing resource if avaliable.

        If the passed resource already has a match in the database then that
        resource is returned. If not then the passed resource is returned.
        """
        existing_resource = get_one(
            BootResource.objects.filter(
                rtype=resource.rtype,
                name=resource.name, architecture=resource.architecture))
        if existing_resource is not None:
            return existing_resource
        return resource

    def create_resource_set(self, resource, label):
        """Creates a new `BootResourceSet` on the given resource."""
        return BootResourceSet.objects.create(
            resource=resource,
            version=resource.get_next_version_name(), label=label)

    def get_resource_filetype(self, value):
        """Convert the upload filetype to the filetype for `BootResource`."""
        if value == 'tgz':
            return BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ
        elif value == 'ddtgz':
            return BOOT_RESOURCE_FILE_TYPE.ROOT_DD

    def create_resource_file(self, resource_set, data):
        """Creates a new `BootResourceFile` on the given resource set."""
        filetype = self.get_resource_filetype(data['filetype'])
        largefile = LargeFile.objects.get_or_create_file_from_content(
            data['content'])
        return BootResourceFile.objects.create(
            resource_set=resource_set, largefile=largefile,
            filename=filetype, filetype=filetype)

    def validate_unique(self):
        """Override to allow the same `BootResource` to already exist.

        This is done because the existing `BootResource` will be used, and a
        new set will be added to that resource.
        """
        # Do nothing, as we do not want to report a uniqueness error.

    def save(self):
        """Persist the boot resource into the database.

        This implementation of `save` does not support the `commit` argument.
        """
        resource = super(BootResourceForm, self).save(commit=False)

        # XXX blake_r 2014-09-22 bug=1361370: Temporarily support the ability
        # to upload a generated image. This should only exist while CentOS and
        # Windows images need to be uploaded, rather than synced or generated.
        if '/' not in resource.name:
            label = 'uploaded'
            resource.rtype = BOOT_RESOURCE_TYPE.UPLOADED
        else:
            label = 'generated'
            resource.rtype = BOOT_RESOURCE_TYPE.GENERATED

        resource = self.get_existing_resource(resource)
        resource.extra = {'subarches': resource.architecture.split('/')[1]}
        if 'title' in self.cleaned_data:
            resource.extra['title'] = self.cleaned_data['title']

        resource.save()
        resource_set = self.create_resource_set(resource, label)
        self.create_resource_file(
            resource_set, self.cleaned_data)
        return resource


class BootResourceNoContentForm(BootResourceForm):
    """Form for uploading boot resources with no content."""

    class Meta:
        model = BootResource
        fields = (
            'name',
            'title',
            'architecture',
            'filetype',
            'sha256',
            'size',
            )

    sha256 = forms.CharField(
        label="SHA256", max_length=64, min_length=64, required=True)

    size = forms.IntegerField(
        label="Size", required=True)

    def __init__(self, *args, **kwargs):
        super(BootResourceNoContentForm, self).__init__(*args, **kwargs)
        # Remove content field, as this form does not use it
        del self.fields['content']

    def create_resource_file(self, resource_set, data):
        """Creates a new `BootResourceFile` on the given resource set."""
        filetype = self.get_resource_filetype(data['filetype'])
        sha256 = data['sha256']
        total_size = data['size']
        largefile = LargeFile.objects.get_file(sha256)
        if largefile is not None:
            if total_size != largefile.total_size:
                raise ValidationError(
                    "File already exists with sha256 that is of "
                    "different size.")
        else:
            # Create an empty large object. It must be opened and closed
            # for the object to be created in the database.
            largeobject = LargeObjectFile()
            largeobject.open().close()
            largefile = LargeFile.objects.create(
                sha256=sha256, total_size=total_size,
                content=largeobject)
        return BootResourceFile.objects.create(
            resource_set=resource_set, largefile=largefile,
            filename=filetype, filetype=filetype)


class ClaimIPForm(Form):
    """Form used to claim an IP address."""
    requested_address = forms.GenericIPAddressField(required=False)


class ClaimIPForMACForm(ClaimIPForm):
    """Form used to claim an IP address for a device or node."""
    mac_address = MACAddressFormField(required=False)


class ReleaseIPForm(Form):
    """Form used to release a device IP address."""
    address = forms.GenericIPAddressField(required=False)

    # unfortunately, we aren't consistent; some APIs just call this "ip"
    ip = forms.GenericIPAddressField(required=False)


class UUID4Field(forms.RegexField):
    """Validates a valid uuid version 4."""

    def __init__(self, *args, **kwargs):
        regex = (
            r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?4[0-9a-fA-F]{3}-?"
            r"[89abAB][0-9a-fA-F]{3}-?[0-9a-fA-F]{12}"
            )
        kwargs['min_length'] = 32
        kwargs['max_length'] = 36
        super(UUID4Field, self).__init__(regex, *args, **kwargs)


class AbsolutePathField(forms.RegexField):
    """Validates an absolute path."""

    def __init__(self, *args, **kwargs):
        regex = r"^(?:/[^/]*)*$"
        kwargs['min_length'] = 1

        # This size comes from linux/limits.h where it defines PATH_MAX = 4096.
        # 4096 includes the nul terminator, so the maximum string length is
        # only 4095 since python does not count the nul terminator.
        kwargs['max_length'] = 4095
        super(AbsolutePathField, self).__init__(regex, *args, **kwargs)


class BytesField(forms.RegexField):
    """Validates and converts a byte value."""

    def __init__(self, *args, **kwargs):
        if "min_value" in kwargs:
            self.min_value = kwargs.pop("min_value")
        else:
            self.min_value = None
        if "max_value" in kwargs:
            self.max_value = kwargs.pop("max_value")
        else:
            self.max_value = None
        regex = r"^-?[0-9]+([KkMmGgTtPpEe]{1})?$"
        super(BytesField, self).__init__(regex, *args, **kwargs)

    def to_python(self, value):
        if value is not None:
            # Make sure the value is a string not an integer.
            value = "%s" % value
        return value

    def clean(self, value):
        value = super(BytesField, self).clean(value)
        if value is not None:
            value = machine_readable_bytes(value)

        # Run validation again, but with the min and max validators. This is
        # because the value has now been converted to an integer.
        self.validators = []
        if self.min_value is not None:
            self.validators.append(MinValueValidator(self.min_value))
        if self.max_value is not None:
            self.validators.append(MaxValueValidator(self.max_value))
        self.run_validators(value)

        return value


class FormatBlockDeviceForm(Form):
    """Form used to format a block device."""
    uuid = UUID4Field(required=False)

    fstype = forms.ChoiceField(
        choices=FILESYSTEM_FORMAT_TYPE_CHOICES, required=True)

    def __init__(self, block_device, *args, **kwargs):
        super(FormatBlockDeviceForm, self).__init__(*args, **kwargs)
        self.block_device = block_device

    def clean(self):
        """Validate block device doesn't have a partition table."""
        # Get the clean_data, check that all of the fields we need are
        # present. If not then the form will error, so no reason to continue.
        cleaned_data = super(FormatBlockDeviceForm, self).clean()
        if 'fstype' not in cleaned_data:
            return cleaned_data
        partition_table = PartitionTable.objects.filter(
            block_device=self.block_device)
        if partition_table.exists():
            raise ValidationError(
                "Cannot format block device with a partition table.")
        return cleaned_data

    def save(self):
        """Persist the `Filesystem` into the database.

        This implementation of `save` does not support the `commit` argument.
        """
        # Remove the previous format if one already exists.
        Filesystem.objects.filter(block_device=self.block_device).delete()

        # Create the new filesystem
        filesystem = Filesystem(
            block_device=self.block_device,
            fstype=self.cleaned_data['fstype'],
            uuid=self.cleaned_data.get('uuid', None))
        filesystem.save()
        return self.block_device


class MountBlockDeviceForm(Form):
    """Form used to mount a block device."""

    mount_point = AbsolutePathField(required=True)

    def __init__(self, block_device, *args, **kwargs):
        super(MountBlockDeviceForm, self).__init__(*args, **kwargs)
        self.block_device = block_device

    def clean(self):
        """Validate block device doesn't have a partition table."""
        # Get the clean_data, check that all of the fields we need are
        # present. If not then the form will error, so no reason to continue.
        cleaned_data = super(MountBlockDeviceForm, self).clean()
        if 'mount_point' not in cleaned_data:
            return cleaned_data
        filesystem = self.block_device.filesystem
        if filesystem is None:
            raise ValidationError(
                "Cannot mount an unformatted block device.")
        if filesystem.filesystem_group is not None:
            raise ValidationError(
                "Filesystem is part of a filesystem group, and cannot be "
                "mounted.")
        return cleaned_data

    def save(self):
        """Persist the `Filesystem` into the database.

        This implementation of `save` does not support the `commit` argument.
        """
        filesystem = self.block_device.filesystem
        filesystem.mount_point = self.cleaned_data['mount_point']
        filesystem.save()
        return self.block_device


class AddPartitionForm(Form):
    """Form used to add a partition to block device."""

    bootable = forms.BooleanField(required=False)
    uuid = UUID4Field(required=False)

    def __init__(self, block_device, *args, **kwargs):
        super(AddPartitionForm, self).__init__(*args, **kwargs)
        self.block_device = block_device
        self.set_up_fields()

    def set_up_fields(self):
        """Create the `size` field.

        This needs to be done on the fly so that we can pass the maximum size.
        """
        self.fields['size'] = BytesField(
            min_value=MIN_BLOCK_DEVICE_SIZE,
            max_value=self.block_device.size,
            required=True)

    def save(self):
        partition_table, _ = PartitionTable.objects.get_or_create(
            block_device=self.block_device)
        return partition_table.add_partition(
            size=self.cleaned_data['size'],
            uuid=self.cleaned_data.get('uuid'),
            bootable=self.cleaned_data.get('bootable'))


class FormatPartitionForm(Form):
    """Form used to format a partition - to add a Filesystem to it."""

    uuid = UUID4Field(required=False)
    fstype = forms.ChoiceField(
        choices=FILESYSTEM_FORMAT_TYPE_CHOICES, required=True)
    label = forms.CharField(required=False)

    def __init__(self, partition, *args, **kwargs):
        super(FormatPartitionForm, self).__init__(*args, **kwargs)
        self.partition = partition

    def save(self):
        """Add the Filesystem to the partition.

        This implementation of `save` does not support the `commit` argument.
        """
        # Remove the previous format if one already exists.
        self.partition.remove_filesystem()
        data = self.cleaned_data
        self.partition.add_filesystem(
            uuid=data['uuid'],
            fstype=data['fstype'],
            label=data['label'])
        return self.partition


class MountPartitionForm(Form):
    """Form used to mount a partition."""

    mount_point = AbsolutePathField(required=True)

    def __init__(self, partition, *args, **kwargs):
        super(MountPartitionForm, self).__init__(*args, **kwargs)
        self.partition = partition

    def clean(self):
        """Validate block device doesn't have a partition table."""
        # Get the clean_data, check that all of the fields we need are
        # present. If not then the form will error, so no reason to continue.
        cleaned_data = super(MountPartitionForm, self).clean()
        if 'mount_point' not in cleaned_data:
            return cleaned_data
        filesystem = self.partition.filesystem
        if filesystem is None:
            raise ValidationError(
                "Cannot mount an unformatted partition.")
        if filesystem.filesystem_group is not None:
            raise ValidationError(
                "Partition is part of a filesystem group, and cannot be "
                "mounted.")
        return cleaned_data

    def save(self):
        """Persist the `Filesystem` into the database.

        This implementation of `save` does not support the `commit` argument.
        """
        filesystem = self.partition.filesystem
        filesystem.mount_point = self.cleaned_data['mount_point']
        filesystem.save()
        return self.partition


class CreatePhysicalBlockDeviceForm(MAASModelForm):
    """For creating physical block device."""

    id_path = AbsolutePathField(required=False)
    size = BytesField(required=True)
    block_size = BytesField(required=True)

    class Meta:
        model = PhysicalBlockDevice
        fields = [
            "name",
            "model",
            "serial",
            "id_path",
            "size",
            "block_size",
        ]

    def __init__(self, node, *args, **kwargs):
        super(CreatePhysicalBlockDeviceForm, self).__init__(*args, **kwargs)
        self.node = node

    def save(self):
        block_device = super(
            CreatePhysicalBlockDeviceForm, self).save(commit=False)
        block_device.node = self.node
        block_device.save()
        return block_device


class UpdatePhysicalBlockDeviceForm(MAASModelForm):
    """For updating physical block device."""

    name = forms.CharField(required=False)
    id_path = AbsolutePathField(required=False)
    size = BytesField(required=False)
    block_size = BytesField(required=False)

    class Meta:
        model = PhysicalBlockDevice
        fields = [
            "name",
            "model",
            "serial",
            "id_path",
            "size",
            "block_size",
        ]


class UpdateVirtualBlockDeviceForm(MAASModelForm):
    """For updating virtual block device."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)
    size = BytesField(required=False)

    class Meta:
        model = VirtualBlockDevice
        fields = [
            "name",
            "uuid",
            "size",
        ]

    def clean(self):
        cleaned_data = super(UpdateVirtualBlockDeviceForm, self).clean()
        is_logical_volume = self.instance.filesystem_group.is_lvm()
        size_has_changed = (
            'size' in self.cleaned_data and
            self.cleaned_data['size'] and
            self.cleaned_data['size'] != self.instance.size)
        if not is_logical_volume and size_has_changed:
            if 'size' in self.errors:
                del self.errors['size']
            raise ValidationError({
                'size': ['Size cannot be changed on this device.']
                })
        return cleaned_data

    def save(self):
        block_device = super(
            UpdateVirtualBlockDeviceForm, self).save(commit=False)
        # blake_r: UUID field will not get set on the model for an unknown
        # reason. Force the updating of the field here.
        if 'uuid' in self.cleaned_data and self.cleaned_data['uuid']:
            block_device.uuid = self.cleaned_data['uuid']
        block_device.save()
        return block_device


def convert_block_device_name_to_id(value):
    """Convert a block device value from an input field into the block device
    id.

    This is used when the user can provide either the ID or the name of the
    block device.

    :param value: User input value.
    :return: The block device ID or original input value if invalid.
    """
    if not value:
        return value
    try:
        value = int(value)
    except ValueError:
        try:
            value = BlockDevice.objects.get(name=value).id
        except BlockDevice.DoesNotExist:
            pass
    return value


def clean_block_device_name_to_id(field):
    """Helper to clean a block device input field.
    See `convert_block_device_name_to_id`."""
    def _convert(self):
        return convert_block_device_name_to_id(self.cleaned_data[field])
    return _convert


def clean_block_device_names_to_ids(field):
    """Helper to clean a block device multi choice input field.
    See `convert_block_device_name_to_id`."""
    def _convert(self):
        return [
            convert_block_device_name_to_id(block_device)
            for block_device in self.cleaned_data[field]
            ]
    return _convert


def convert_partition_name_to_id(value):
    """Convert a partition value from an input field into the partition id.

    This is used when the user can provide either the ID or the name of the
    partition.

    :param value: User input value.
    :return: The partition ID or original input value if invalid.
    """
    if not value:
        return value
    try:
        partition = Partition.objects.get_partition_by_id_or_name(value)
    except Partition.DoesNotExist:
        return value
    return partition.id


def clean_partition_name_to_id(field):
    """Helper to clean a partition input field.
    See `convert_partition_name_to_id`."""
    def _convert(self):
        return convert_partition_name_to_id(self.cleaned_data[field])
    return _convert


def clean_partition_names_to_ids(field):
    """Helper to clean a partition multi choice input field.
    See `convert_partition_name_to_id`."""
    def _convert(self):
        return [
            convert_partition_name_to_id(partition)
            for partition in self.cleaned_data[field]
            ]
    return _convert


class CreateBcacheForm(Form):
    """For validaing and saving a new Bcache."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)
    cache_device = forms.ChoiceField(required=False)
    backing_device = forms.ChoiceField(required=False)
    cache_partition = forms.ChoiceField(required=False)
    backing_partition = forms.ChoiceField(required=False)
    cache_mode = forms.ChoiceField(
        choices=CACHE_MODE_TYPE_CHOICES, required=True)

    clean_cache_device = clean_block_device_name_to_id('cache_device')
    clean_backing_device = clean_block_device_name_to_id('backing_device')
    clean_cache_partition = clean_partition_name_to_id('cache_partition')
    clean_backing_partition = clean_partition_name_to_id('backing_partition')

    def __init__(self, node, *args, **kwargs):
        super(CreateBcacheForm, self).__init__(*args, **kwargs)
        self.node = node
        self._set_up_field_choices()

    def clean(self):
        """Makes sure the Bcache is sensible."""
        cleaned_data = super(CreateBcacheForm, self).clean()

        Bcache.objects.validate_bcache_creation_parameters(
            cache_mode=self.cleaned_data.get('cache_mode'),
            cache_device=self.cleaned_data.get('cache_device'),
            cache_partition=self.cleaned_data.get('cache_partition'),
            backing_device=self.cleaned_data.get('backing_device'),
            backing_partition=self.cleaned_data.get('backing_partition'),
            validate_mode=False)  # Cache mode is validated by the field.

        return cleaned_data

    def save(self):
        """Persist the bcache into the database.

        This implementation of `save` does not support the `commit` argument.
        """

        cache_partition = cache_device = None
        if self.cleaned_data['cache_device']:
            cache_device = BlockDevice.objects.get(
                id=self.cleaned_data['cache_device'])
        elif self.cleaned_data['cache_partition']:
            cache_partition = Partition.objects.get(
                id=self.cleaned_data['cache_partition'])

        backing_partition = backing_device = None
        if self.cleaned_data['backing_device']:
            backing_device = BlockDevice.objects.get(
                id=self.cleaned_data['backing_device'])
        elif self.cleaned_data['backing_partition']:
            backing_partition = Partition.objects.get(
                id=self.cleaned_data['backing_partition'])

        return Bcache.objects.create_bcache(
            name=self.cleaned_data['name'],
            uuid=self.cleaned_data['uuid'],
            cache_device=cache_device,
            backing_device=backing_device,
            cache_partition=cache_partition,
            backing_partition=backing_partition,
            cache_mode=self.cleaned_data['cache_mode'])

    def _set_up_field_choices(self):
        """Sets up choices for `cache_device`, `backing_device`,
        `cache_partition` and `backing_partition` fields."""

        # Select the unused, non-partitioned block devices of this node.
        free_block_devices = list(
            BlockDevice.objects.get_free_block_devices_for_node(self.node))
        block_device_choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ]

        # Select the unused partitions of this node.
        free_partitions = list(
            Partition.objects.get_free_partitions_for_node(self.node))
        partition_choices = [
            (partition.id, partition.name)
            for partition in free_partitions
        ] + [
            (partition.name, partition.name)
            for partition in free_partitions
        ]

        self.fields['cache_device'].choices = block_device_choices
        self.fields['cache_partition'].choices = partition_choices
        self.fields['backing_device'].choices = block_device_choices
        self.fields['backing_partition'].choices = partition_choices


class UpdateBcacheForm(Form):
    """For validaing and saving an existing Bcache."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)
    cache_device = forms.ChoiceField(required=False)
    backing_device = forms.ChoiceField(required=False)
    cache_partition = forms.ChoiceField(required=False)
    backing_partition = forms.ChoiceField(required=False)
    cache_mode = forms.ChoiceField(
        choices=CACHE_MODE_TYPE_CHOICES, required=False)

    clean_cache_device = clean_block_device_name_to_id('cache_device')
    clean_backing_device = clean_block_device_name_to_id('backing_device')
    clean_cache_partition = clean_partition_name_to_id('cache_partition')
    clean_backing_partition = clean_partition_name_to_id('backing_partition')

    def __init__(self, bcache, *args, **kwargs):
        super(UpdateBcacheForm, self).__init__(*args, **kwargs)
        self.bcache = bcache
        self.node = bcache.get_node()
        self._set_up_field_choices()

    def save(self):
        """Persist the bcache into the database.

        This implementation of `save` does not support the `commit` argument.
        """

        if self.cleaned_data['cache_device']:
            device = BlockDevice.objects.get(
                id=int(self.cleaned_data['cache_device']), node=self.node)
            # Remove previous cache
            self.bcache.filesystems.filter(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE).delete()
            # Create a new one on this device.
            self.bcache.filesystems.add(Filesystem.objects.create(
                block_device=device, fstype=FILESYSTEM_TYPE.BCACHE_CACHE))
        elif self.cleaned_data['cache_partition']:
            partition = Partition.objects.get(
                id=int(self.cleaned_data['cache_partition']))
            # Remove previous cache
            self.bcache.filesystems.filter(
                fstype=FILESYSTEM_TYPE.BCACHE_CACHE).delete()
            # Create a new one on this partition.
            self.bcache.filesystems.add(Filesystem.objects.create(
                partition=partition, fstype=FILESYSTEM_TYPE.BCACHE_CACHE))

        if self.cleaned_data['backing_device']:
            device = BlockDevice.objects.get(
                id=int(self.cleaned_data['backing_device']))
            # Remove previous cache
            self.bcache.filesystems.filter(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING).delete()
            # Create a new one on this device.
            self.bcache.filesystems.add(Filesystem.objects.create(
                block_device=device, fstype=FILESYSTEM_TYPE.BCACHE_BACKING))
        elif self.cleaned_data['backing_partition']:
            partition = Partition.objects.get(
                id=int(self.cleaned_data['backing_partition']))
            # Remove previous cache
            self.bcache.filesystems.filter(
                fstype=FILESYSTEM_TYPE.BCACHE_BACKING).delete()
            # Create a new one on this partition.
            self.bcache.filesystems.add(Filesystem.objects.create(
                partition=partition, fstype=FILESYSTEM_TYPE.BCACHE_BACKING))

        if self.cleaned_data['name']:
            self.bcache.name = self.cleaned_data['name']
        if self.cleaned_data['uuid']:
            self.bcache.uuid = self.cleaned_data['uuid']
        if self.cleaned_data['cache_mode']:
            self.bcache.cache_mode = self.cleaned_data['cache_mode']

        self.bcache.save()

        return self.bcache

    def _set_up_field_choices(self):
        """Sets up choices for `cache_device`, `backing_device`,
        `cache_partition` and `backing_partition` fields."""

        # Select the unused, non-partitioned block devices of this node, append
        # the ones currently used by bcache and exclude the virtual block
        # device created by the cache.
        free_block_devices = (
            BlockDevice.objects.get_free_block_devices_for_node(
                self.node).exclude(id=self.bcache.virtual_device.id))
        current_block_devices = self.bcache.filesystems.exclude(
            block_device=None)
        block_device_choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ] + [
            (fs.block_device_id, fs.block_device.name)
            for fs in current_block_devices
        ] + [
            (fs.block_device.name, fs.block_device.name)
            for fs in current_block_devices
        ]

        # Select the unused partitions of this node, append the bcache ones (if
        # they exist).
        free_partitions = Partition.objects.get_free_partitions_for_node(
            self.node)
        current_partitions = self.bcache.filesystems.exclude(partition=None)
        partition_choices = [
            (partition.id, partition.name)
            for partition in free_partitions
        ] + [
            (partition.name, partition.name)
            for partition in free_partitions
        ] + [
            (fs.partition_id, fs.partition.name)
            for fs in current_partitions
        ] + [
            (fs.partition.name, fs.partition.name)
            for fs in current_partitions
        ]

        self.fields['cache_device'].choices = block_device_choices
        self.fields['cache_partition'].choices = partition_choices
        self.fields['backing_device'].choices = block_device_choices
        self.fields['backing_partition'].choices = partition_choices


class CreateRaidForm(Form):
    """For validating and saving a new RAID."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)
    level = forms.ChoiceField(
        choices=FILESYSTEM_GROUP_RAID_TYPE_CHOICES, required=True)
    block_devices = forms.MultipleChoiceField(required=False)
    partitions = forms.MultipleChoiceField(required=False)
    spare_devices = forms.MultipleChoiceField(required=False)
    spare_partitions = forms.MultipleChoiceField(required=False)

    clean_block_devices = clean_block_device_names_to_ids('block_devices')
    clean_partitions = clean_partition_names_to_ids('partitions')
    clean_spare_devices = clean_block_device_names_to_ids('spare_devices')
    clean_spare_partitions = clean_partition_names_to_ids('spare_partitions')

    def _set_up_field_choices(self):
        """Sets up the `block_devices`, `partition`, `spare_devices` and
        `spare_partitions` fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        partitions and block devices that fit this node.

        """
        # Select the unused, non-partitioned block devices of this node.
        free_block_devices = (
            BlockDevice.objects.get_free_block_devices_for_node(
                self.node))
        block_device_choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ]

        # Select the unused partitions of this node.
        free_partitions = Partition.objects.get_free_partitions_for_node(
            self.node)
        partition_choices = [
            (partition.id, partition.name)
            for partition in free_partitions
        ] + [
            (partition.name, partition.name)
            for partition in free_partitions
        ]

        self.fields['block_devices'].choices = block_device_choices
        self.fields['partitions'].choices = partition_choices
        self.fields['spare_devices'].choices = block_device_choices
        self.fields['spare_partitions'].choices = partition_choices

    def __init__(self, node, *args, **kwargs):
        super(CreateRaidForm, self).__init__(*args, **kwargs)
        self.node = node
        self._set_up_field_choices()

    def clean(self):
        cleaned_data = super(CreateRaidForm, self).clean()
        # It is not possible to create a RAID without any devices or
        # partitions, but we catch this situation here in order to provide a
        # clearer error message.
        if ('block_devices' in cleaned_data and 'partitions' in cleaned_data
                and len(
                    cleaned_data['block_devices'] + cleaned_data['partitions'])
                == 0):
            raise ValidationError(
                'At least one block device or partition must be added to the '
                'array.')
        return cleaned_data

    def save(self):
        """Persist the RAID into the database.

        This implementation of `save` does not support the `commit` argument.
        """

        block_devices = BlockDevice.objects.filter(
            id__in=self.cleaned_data['block_devices'])
        partitions = Partition.objects.filter(
            id__in=self.cleaned_data['partitions'])
        spare_devices = BlockDevice.objects.filter(
            id__in=self.cleaned_data['spare_devices'])
        spare_partitions = Partition.objects.filter(
            id__in=self.cleaned_data['spare_partitions'])

        return RAID.objects.create_raid(
            name=self.cleaned_data['name'],
            level=self.cleaned_data['level'],
            uuid=self.cleaned_data['uuid'],
            block_devices=block_devices,
            partitions=partitions,
            spare_devices=spare_devices,
            spare_partitions=spare_partitions
        )


class UpdateRaidForm(Form):
    """Form for updating a RAID."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)

    add_block_devices = forms.MultipleChoiceField(required=False)
    add_partitions = forms.MultipleChoiceField(required=False)
    add_spare_devices = forms.MultipleChoiceField(required=False)
    add_spare_partitions = forms.MultipleChoiceField(required=False)

    remove_block_devices = forms.MultipleChoiceField(required=False)
    remove_partitions = forms.MultipleChoiceField(required=False)
    remove_spare_devices = forms.MultipleChoiceField(required=False)
    remove_spare_partitions = forms.MultipleChoiceField(required=False)

    clean_add_block_devices = clean_block_device_names_to_ids(
        'add_block_devices')
    clean_add_partitions = clean_partition_names_to_ids(
        'add_partitions')
    clean_add_spare_devices = clean_block_device_names_to_ids(
        'add_spare_devices')
    clean_add_spare_partitions = clean_partition_names_to_ids(
        'add_spare_partitions')

    clean_remove_block_devices = clean_block_device_names_to_ids(
        'remove_block_devices')
    clean_remove_partitions = clean_partition_names_to_ids(
        'remove_partitions')
    clean_remove_spare_devices = clean_block_device_names_to_ids(
        'remove_spare_devices')
    clean_remove_spare_partitions = clean_partition_names_to_ids(
        'remove_spare_partitions')

    def __init__(self, raid, *args, **kwargs):
        super(UpdateRaidForm, self).__init__(*args, **kwargs)
        self.raid = raid
        self.set_up_field_choices()

    def set_up_field_choices(self):
        """Sets up the `add_block_devices`, `add_partitions`,
        `add_spare_devices`, add_spare_partitions`, `remove_block_devices`,
        `remove_partition`, `remove_spare_devices`, `remove_spare_partitions`
        fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        partitions and block devices that fit this node.

        """
        node = self.raid.get_node()

        # Select the unused, non-partitioned block devices of this node.
        free_block_devices = (
            BlockDevice.objects.get_free_block_devices_for_node(node))
        add_block_device_choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ]

        # Select the unused partitions of this node.
        free_partitions = Partition.objects.get_free_partitions_for_node(node)
        add_partition_choices = [
            (p.id, p.name)
            for p in free_partitions
        ] + [
            (p.name, p.name)
            for p in free_partitions
        ]

        # Select the used block devices of this RAID.
        current_block_devices = self.raid.filesystems.exclude(
            block_device=None)
        remove_block_device_choices = [
            (fs.block_device.id, fs.block_device.name)
            for fs in current_block_devices
        ] + [
            (fs.block_device.name, fs.block_device.name)
            for fs in current_block_devices
        ]

        # Select the used partitions of this RAID.
        current_partitions = self.raid.filesystems.exclude(partition=None)
        remove_partition_choices = [
            (fs.partition.id, fs.partition.name)
            for fs in current_partitions
        ] + [
            (fs.partition.name, fs.partition.name)
            for fs in current_partitions
        ]

        # Sets up the choices for additive fields.
        self.fields['add_block_devices'].choices = add_block_device_choices
        self.fields['add_partitions'].choices = add_partition_choices
        self.fields['add_spare_devices'].choices = add_block_device_choices
        self.fields['add_spare_partitions'].choices = add_partition_choices

        # Sets up the choices for removal fields.
        self.fields['remove_block_devices'].choices = (
            remove_block_device_choices)
        self.fields['remove_partitions'].choices = remove_partition_choices
        self.fields['remove_spare_devices'].choices = (
            remove_block_device_choices)
        self.fields['remove_spare_partitions'].choices = (
            remove_partition_choices)

    def save(self):
        """Save updates to the RAID.

        This implementation of `save` does not support the `commit` argument.
        """

        current_block_device_ids = [
            fs.block_device.id for fs in self.raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID).exclude(block_device=None)
        ]
        current_spare_device_ids = [
            fs.block_device.id for fs in self.raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID_SPARE).exclude(block_device=None)
        ]
        current_partition_ids = [
            fs.partition.id for fs in self.raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID).exclude(partition=None)
        ]
        current_spare_partition_ids = [
            fs.partition.id for fs in self.raid.filesystems.filter(
                fstype=FILESYSTEM_TYPE.RAID_SPARE).exclude(partition=None)
        ]

        for device_id in (
                self.cleaned_data['remove_block_devices'] +
                self.cleaned_data['remove_spare_devices']):
            if (device_id in current_block_device_ids
                    + current_spare_device_ids):
                self.raid.remove_device(BlockDevice.objects.get(id=device_id))

        for partition_id in (
                self.cleaned_data['remove_partitions'] +
                self.cleaned_data['remove_spare_partitions']):
            if (partition_id in current_partition_ids
                    + current_spare_partition_ids):
                self.raid.remove_partition(
                    Partition.objects.get(id=partition_id))

        for device_id in self.cleaned_data['add_block_devices']:
            if device_id not in current_block_device_ids:
                self.raid.add_device(
                    BlockDevice.objects.get(id=device_id),
                    FILESYSTEM_TYPE.RAID)

        for device_id in self.cleaned_data['add_spare_devices']:
            if device_id not in current_block_device_ids:
                self.raid.add_device(
                    BlockDevice.objects.get(id=device_id),
                    FILESYSTEM_TYPE.RAID_SPARE)

        for partition_id in self.cleaned_data['add_partitions']:
            if partition_id not in current_partition_ids:
                self.raid.add_partition(
                    Partition.objects.get(id=partition_id),
                    FILESYSTEM_TYPE.RAID)

        for partition_id in self.cleaned_data['add_spare_partitions']:
            if partition_id not in current_partition_ids:
                self.raid.add_partition(
                    Partition.objects.get(id=partition_id),
                    FILESYSTEM_TYPE.RAID_SPARE)

        # The simple attributes
        if 'name' in self.cleaned_data and self.cleaned_data['name']:
            self.raid.name = self.cleaned_data['name']

        if 'uuid' in self.cleaned_data and self.cleaned_data['uuid']:
            self.raid.uuid = self.cleaned_data['uuid']

        self.raid.save()
        return self.raid


class CreateVolumeGroupForm(Form):
    """For validating and saving a new volume group."""

    name = forms.CharField(required=True)
    uuid = UUID4Field(required=False)
    block_devices = forms.MultipleChoiceField(required=False)
    partitions = forms.MultipleChoiceField(required=False)

    clean_block_devices = clean_block_device_names_to_ids('block_devices')
    clean_partitions = clean_partition_names_to_ids('partitions')

    def __init__(self, node, *args, **kwargs):
        super(CreateVolumeGroupForm, self).__init__(*args, **kwargs)
        self.node = node
        self.set_up_choice_fields()

    def set_up_choice_fields(self):
        """Sets up the choice fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        partitions and block devices that fit this node.
        """
        # Select the unused, non-partitioned block devices of this node.
        free_block_devices = (
            BlockDevice.objects.get_free_block_devices_for_node(
                self.node))
        self.fields['block_devices'].choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ]
        # Select the unused partitions of this node.
        free_partitions = Partition.objects.get_free_partitions_for_node(
            self.node)
        self.fields['partitions'].choices = [
            (partition.id, partition.name)
            for partition in free_partitions
        ] + [
            (partition.name, partition.name)
            for partition in free_partitions
        ]

    def clean(self):
        """Validate that at least one block device or partition is given."""
        cleaned_data = super(CreateVolumeGroupForm, self).clean()
        if "name" not in cleaned_data:
            return cleaned_data
        has_block_devices = (
            "block_devices" in cleaned_data and
            len(cleaned_data["block_devices"]) > 0)
        has_partitions = (
            "partitions" in cleaned_data and
            len(cleaned_data["partitions"]) > 0)
        has_block_device_and_partition_errors = (
            "block_devices" in self._errors or "partitions" in self._errors)
        if (not has_block_devices and
                not has_partitions and
                not has_block_device_and_partition_errors):
            raise ValidationError(
                "At least one valid block device or partition is required.")
        return cleaned_data

    def save(self):
        """Persist the `VolumeGroup` into the database.

        This implementation of `save` does not support the `commit` argument.
        """
        block_device_ids = self.cleaned_data['block_devices']
        partition_ids = self.cleaned_data['partitions']
        return VolumeGroup.objects.create_volume_group(
            name=self.cleaned_data['name'],
            uuid=self.cleaned_data.get('uuid'),
            block_devices=BlockDevice.objects.filter(id__in=block_device_ids),
            partitions=Partition.objects.filter(id__in=partition_ids))


class UpdateVolumeGroupForm(Form):
    """For validating and updating a new volume group."""

    name = forms.CharField(required=False)
    uuid = UUID4Field(required=False)
    add_block_devices = forms.MultipleChoiceField(required=False)
    remove_block_devices = forms.MultipleChoiceField(required=False)
    add_partitions = forms.MultipleChoiceField(required=False)
    remove_partitions = forms.MultipleChoiceField(required=False)

    clean_add_block_devices = clean_block_device_names_to_ids(
        'add_block_devices')
    clean_remove_block_devices = clean_block_device_names_to_ids(
        'remove_block_devices')
    clean_add_partitions = clean_partition_names_to_ids(
        'add_partitions')
    clean_remove_partitions = clean_partition_names_to_ids(
        'remove_partitions')

    def __init__(self, volume_group, *args, **kwargs):
        super(UpdateVolumeGroupForm, self).__init__(*args, **kwargs)
        self.volume_group = volume_group
        self.set_up_choice_fields()

    def set_up_choice_fields(self):
        """Sets up the choice fields.

        This needs to be done on the fly so that we can pass a dynamic list of
        partitions and block devices that fit this node.
        """
        node = self.volume_group.get_node()
        # Select the unused, non-partitioned block devices of this node.
        free_block_devices = (
            BlockDevice.objects.get_free_block_devices_for_node(
                node))
        self.fields['add_block_devices'].choices = [
            (bd.id, bd.name)
            for bd in free_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in free_block_devices
        ]
        # Select the unused partitions of this node.
        free_partitions = Partition.objects.get_free_partitions_for_node(
            node)
        self.fields['add_partitions'].choices = [
            (partition.id, partition.name)
            for partition in free_partitions
        ] + [
            (partition.name, partition.name)
            for partition in free_partitions
        ]
        # Select the block devices in the volume group.
        used_block_devices = (
            BlockDevice.objects.get_block_devices_in_filesystem_group(
                self.volume_group))
        self.fields['remove_block_devices'].choices = [
            (bd.id, bd.name)
            for bd in used_block_devices
        ] + [
            (bd.name, bd.name)
            for bd in used_block_devices
        ]
        # Select the current partitions in the volume group.
        used_partitions = (
            Partition.objects.get_partitions_in_filesystem_group(
                self.volume_group))
        self.fields['remove_partitions'].choices = [
            (partition.id, partition.name)
            for partition in used_partitions
        ] + [
            (partition.name, partition.name)
            for partition in used_partitions
        ]

    def save(self):
        """Update the `VolumeGroup`.

        This implementation of `save` does not support the `commit` argument.
        """
        if 'name' in self.cleaned_data and self.cleaned_data['name']:
            self.volume_group.name = self.cleaned_data['name']
        if 'uuid' in self.cleaned_data and self.cleaned_data['uuid']:
            self.volume_group.uuid = self.cleaned_data['uuid']

        # Create the new list of block devices.
        add_block_device_ids = self.cleaned_data['add_block_devices']
        remove_block_device_ids = self.cleaned_data['remove_block_devices']
        block_devices = (
            BlockDevice.objects.get_block_devices_in_filesystem_group(
                self.volume_group))
        block_devices = [
            block_device
            for block_device in block_devices
            if block_device.id not in remove_block_device_ids
            ]
        block_devices = block_devices + list(
            BlockDevice.objects.filter(id__in=add_block_device_ids))

        # Create the new list of partitions.
        add_partition_ids = self.cleaned_data['add_partitions']
        remove_partition_ids = self.cleaned_data['remove_partitions']
        partitions = (
            Partition.objects.get_partitions_in_filesystem_group(
                self.volume_group))
        partitions = [
            partition
            for partition in partitions
            if partition.id not in remove_partition_ids
            ]
        partitions = partitions + list(
            Partition.objects.filter(id__in=add_partition_ids))

        # Update the block devices and partitions in the volume group.
        self.volume_group.update_block_devices_and_partitions(
            block_devices, partitions)
        self.volume_group.save()
        return self.volume_group


class CreateLogicalVolumeForm(Form):
    """Form used to add a logical volume to a volume group."""

    name = forms.CharField(required=True)
    uuid = UUID4Field(required=False)

    def __init__(self, volume_group, *args, **kwargs):
        super(CreateLogicalVolumeForm, self).__init__(*args, **kwargs)
        self.volume_group = volume_group
        self.set_up_fields()

    def set_up_fields(self):
        """Create the `size` fields.

        This needs to be done on the fly so that we can pass the maximum size.
        """
        self.fields['size'] = BytesField(
            min_value=MIN_BLOCK_DEVICE_SIZE,
            max_value=self.volume_group.get_lvm_free_space(),
            required=True)

    def clean(self):
        """Validate that at least one block device or partition is given."""
        cleaned_data = super(CreateLogicalVolumeForm, self).clean()
        if self.volume_group.get_lvm_free_space() < MIN_BLOCK_DEVICE_SIZE:
            # Remove the size errors. They are confusing because the
            # minimum is larger than the maximum.
            if "size" in self._errors:
                del self._errors["size"]
            raise ValidationError(
                "Volume group (%s) cannot hold any more logical volumes, "
                "because it doesn't have enough free space." % (
                    self.volume_group.name))
        return cleaned_data

    def save(self):
        return self.volume_group.create_logical_volume(
            name=self.cleaned_data['name'],
            uuid=self.cleaned_data.get('uuid'),
            size=self.cleaned_data['size'])
