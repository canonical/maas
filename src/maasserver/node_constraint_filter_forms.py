# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'AcquireNodeForm',
    ]


from abc import (
    ABCMeta,
    abstractmethod,
)
from collections import defaultdict
import itertools
from itertools import chain
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from maasserver.fields import mac_validator
from maasserver.forms import (
    MultipleChoiceField,
    UnconstrainedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
import maasserver.forms as maasserver_forms
from maasserver.models import (
    PhysicalBlockDevice,
    Subnet,
    Tag,
    VLAN,
    Zone,
)
from maasserver.models.subnet import SUBNET_NAME_VALIDATOR
from maasserver.models.zone import ZONE_NAME_VALIDATOR
from maasserver.utils.orm import (
    macs_contain,
    macs_do_not_contain,
)
from netaddr import IPAddress
from netaddr.core import AddrFormatError

# Matches the storage constraint from Juju. Format is an optional label,
# followed by an optional colon, then size (which is mandatory) followed by an
# optional comma seperated list of tags in parentheses.
#
# Examples:
#
#     200(ssd,removable),400(ssd),300
#      - 200GB disk with ssd and removable tag
#      - 400GB disk with ssd tag
#      - 300GB disk
#
#     root:80(ssd),data:400
#      - 80+GB disk with ssd tag, name the constraint "root"
#      - 400+GB disk, name the consrtaint "data"
STORAGE_REGEX = re.compile(
    r"(?:(?P<label>[a-zA-Z0-9]+)\:)?"  # Optional label
    "(?P<size>[0-9.]+)"                # Mandatory size
    "(?:\((?P<tags>[^)]+)\))?",        # Optional tag list between parentheses
    re.VERBOSE)


def storage_validator(value):
    """Validate the storage constraint.

    Check whether value is accurately parsed.

    Validation is done by parsing the storage constraint string and
    reassembling it from the parsed data. Due to the rules employed, the only
    way the original and the generated can differ is if the original has extra
    elements that could not be parsed and is, therefore, invalid.
    """
    if value is None or value == "":
        return
    groups = STORAGE_REGEX.findall(value)
    if not groups:
        raise ValidationError('Malformed storage constraint, "%s".' % value)
    rendered_groups = []
    for name, size, tags in groups:  # For each parsed constraint
        group = ""
        if name != "":
            group = name + ":"       # start with the constraint name
        group += size                # add the size part
        if tags != "":
            group += "(%s)" % tags   # add the tags, if present
        rendered_groups.append(group)
    if ','.join(rendered_groups) != value:
        raise ValidationError('Malformed storage constraint, "%s".' % value)


def generate_architecture_wildcards(arches):
    """Map 'primary' architecture names to a list of full expansions.

    Return a dictionary keyed by the primary architecture name (the part before
    the '/'). The value of an entry is a frozenset of full architecture names
    ('primary_arch/subarch') under the keyed primary architecture.
    """
    sorted_arch_list = sorted(arches)

    def extract_primary_arch(arch):
        return arch.split('/')[0]

    return {
        primary_arch: frozenset(subarch_generator)
        for primary_arch, subarch_generator in itertools.groupby(
            sorted_arch_list, key=extract_primary_arch
        )
    }


def get_architecture_wildcards(arches):
    wildcards = generate_architecture_wildcards(arches)
    # juju uses a general "arm" architecture constraint across all of its
    # providers. Since armhf is the cross-distro agreed Linux userspace
    # architecture and ABI and ARM servers are expected to only use armhf,
    # interpret "arm" to mean "armhf" in MAAS.
    if 'armhf' in wildcards and 'arm' not in wildcards:
        wildcards['arm'] = wildcards['armhf']
    return wildcards


def parse_legacy_tags(values):
    # Support old-method to pass a list of strings using a
    # comma-separated or space-separated list.
    # 'values' is assumed to be a list of strings.
    result = chain.from_iterable(
        re.findall(r'[^\s,]+', value) for value in values)
    return list(result)


# Mapping used to rename the fields from the AcquireNodeForm form.
# The new names correspond to the names used by Juju.  This is used so
# that the search form present on the node listing page can be used to
# filter nodes using Juju's semantics.
JUJU_ACQUIRE_FORM_FIELDS_MAPPING = {
    'name': 'maas-name',
    'tags': 'maas-tags',
    'arch': 'architecture',
    'cpu_count': 'cpu',
    'storage': 'storage',
}


# XXX JeroenVermeulen 2014-02-06: Can we document this please?
class RenamableFieldsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(RenamableFieldsForm, self).__init__(*args, **kwargs)
        self.field_mapping = {name: name for name in self.fields}

    def get_field_name(self, name):
        """Get the new name of the field named 'name'."""
        return self.field_mapping[name]

    def rename_fields(self, mapping):
        """Rename all the field as described in the given mapping."""
        for old_name, new_name in mapping.items():
            self.rename_field(old_name, new_name)

    def rename_field(self, old_name, new_name):
        """Rename a field."""
        if old_name in self.fields:
            # Rename field mapping.
            self.field_mapping[old_name] = new_name

            # Rename field.
            self.fields[new_name] = self.fields.pop(old_name)

            # Rename clean_field() method if it exists.
            clean_name = "clean_%s" % old_name
            method = getattr(self, clean_name, None)
            if method is not None:
                setattr(self, "clean_%s" % new_name, method)


def detect_nonexistent_zone_names(names):
    """Check for, and return, names of nonexistent physical zones.

    Used for checking zone names as passed to the `AcquireNodeForm`.

    :param names: List, tuple, or set of purpoprted zone names.
    :return: A sorted list of those names that did not name existing zones.
    """
    assert isinstance(names, (list, tuple, set))
    if len(names) == 0:
        return []
    existing_names = set(Zone.objects.all().values_list('name', flat=True))
    return sorted(set(names) - existing_names)


def describe_single_constraint_value(value):
    """Return an atomic constraint value as human-readable text.

    :param value: Simple form value for some constraint.
    :return: String representation of `value`, or `None` if the value
        means that the constraint was not set.
    """
    if value is None or value == '':
        return None
    else:
        return '%s' % value


def describe_multi_constraint_value(value):
    """Return a multi-valued constraint value as human-readable text.

    :param value: Sequence form value for some constraint.
    :return: String representation of `value`, or `None` if the value
        means that the constraint was not set.
    """
    if value is None or len(value) == 0:
        return None
    else:
        if isinstance(value, (set, dict, frozenset)):
            # Order unordered containers for consistency.
            sequence = sorted(value)
        else:
            # Keep ordered containers in their original order.
            sequence = value
        return ','.join(map(describe_single_constraint_value, sequence))


def get_storage_constraints_from_string(storage):
    """Return sorted list of storage constraints from the given string."""
    groups = STORAGE_REGEX.findall(storage)
    if not groups:
        return None

    # Sort constraints so the disk with the largest number of tags come
    # first. This is so the most specific disk is selected before the others.
    constraints = [
        (
            label,
            int(float(size) * (1000 ** 3)),
            tags.split(',') if tags != '' else None,
        )
        for (label, size, tags) in groups
        ]
    count_tags = lambda (label, size, tags): 0 if tags is None else len(tags)
    head, tail = constraints[:1], constraints[1:]
    tail.sort(key=count_tags, reverse=True)
    return head + tail


def nodes_by_storage(storage):
    """Return list of dicts describing matching nodes and matched block devices

    For a constraint string like "root:30(ssd),data:1000(rotary,5400rpm)", we'd
    return a dictionary like:

    {123: {12345: "root", 12346: "data"},
     124: {...}.
     ...
    }

    Where the "123" and "124" keys are node_ids and the inner dict keys (12345,
    12346) contain the name of the constraint that matched the device

    The first constraint always refers to the block device that has the lowest
    id. The remaining constraints can match any device of that node

    """
    constraints = get_storage_constraints_from_string(storage)
    # Return early if no constraints were given
    if constraints is None:
        return None
    matches = defaultdict(dict)
    root_device = True  # The 1st constraint refers to the node's 1st device
    for constraint_name, size, tags in constraints:
        if root_device:
            # Sort the `PhysicalBlockDevice`s by id because we consider the
            # first device as the root device.
            root_device = False
            matched_devices = PhysicalBlockDevice.objects.all().order_by('id')
            matched_devices = matched_devices.values(
                'id', 'node_id', 'size', 'tags')

            # Only keep the first device for every node. This is done to make
            # sure filtering out the size and tags is not done to all the
            # block devices. This should only be done to the first block
            # device.
            found_nodes = set()
            devices = []
            for device in matched_devices:
                if device['node_id'] in found_nodes:
                    continue
                devices.append(device)
                found_nodes.add(device['node_id'])

            # Remove the devices that are not of correct size and the devices
            # that are missing the correct tags or label.
            devices = [
                device
                for device in devices
                if device['size'] >= size
                ]
            if tags is not None:
                tags = set(tags)
                devices = [
                    device
                    for device in devices
                    if tags.issubset(set(device['tags']))
                    ]
            matched_devices = devices
        else:
            # Query for the `PhysicalBlockDevice`s that have the closest size
            # and, if specified, the given tags.
            if tags is None:
                matched_devices = PhysicalBlockDevice.objects.filter(
                    size__gte=size).order_by('size')
            else:
                matched_devices = PhysicalBlockDevice.objects.filter_by_tags(
                    tags).filter(size__gte=size)
            matched_devices = matched_devices.order_by('size')
            matched_devices = matched_devices.values(
                'id', 'node_id', 'size', 'tags')

        # Loop through all the returned devices. Insert only the first
        # device from each node into `matches`.
        matched_in_loop = []
        for device in matched_devices:
            device_id = device['id']
            device_node_id = device['node_id']

            if device_node_id in matched_in_loop:
                continue
            if device_id in matches[device_node_id]:
                continue
            matches[device_node_id][device_id] = constraint_name
            matched_in_loop.append(device_node_id)

    # Return only the nodes that have the correct number of disks.
    nodes = {
        node_id: {
            disk_id: name
            for disk_id, name in disks.items()
            if name != ''  # Map only those w/ named constraints
        }
        for node_id, disks in matches.items()
        if len(disks) == len(constraints)
    }
    return nodes


def strip_type_tag(type_tag, specifier):
    """Return a network specifier minus its type tag."""
    prefix = type_tag + ':'
    assert specifier.startswith(prefix)
    return specifier[len(prefix):]


class SubnetSpecifier:
    """A :class:`SubnetSpecifier` identifies a :class:`Subnet`.

    For example, in placement constraints, a user may specify that a node
    must be attached to a certain subnet.  They identify the subnet through
    a subnet specifier, which may be its name (`dmz`), an IP address
    (`ip:10.12.0.0`), or a VLAN tag (`vlan:15` or `vlan:0xf`).

    Each type of subnet specifier has its own `SubnetSpecifier`
    implementation class.  The class constructor validates and parses a
    subnet specifier of its type, and the object knows how to retrieve
    whatever subnet it identifies from the database.
    """
    __metaclass__ = ABCMeta

    # Most subnet specifiers start with a type tag followed by a colon, e.g.
    # "ip:10.1.0.0".
    type_tag = None

    @abstractmethod
    def find_subnet(self):
        """Load the identified :class:`Subnet` from the database.

        :raise Subnet.DoesNotExist: If no subnet matched the specifier.
        :return: The :class:`Subnet`.
        """


class NameSpecifier(SubnetSpecifier):
    """Identify a subnet by its name.

    This type of subnet specifier has no type tag; it's just the name.  A
    subnet name cannot contain colon (:) characters.
    """

    def __init__(self, spec):
        SUBNET_NAME_VALIDATOR(spec)
        self.name = spec

    def find_subnet(self):
        return Subnet.objects.get(name=self.name)


class IPSpecifier(SubnetSpecifier):
    """Identify a subnet by any IP address it contains.

    The IP address is prefixed with a type tag `ip:`, e.g. `ip:10.1.1.0`.
    It can name any IP address within the subnet, including its base address,
    its broadcast address, or any host address that falls in its IP range.
    """
    type_tag = 'ip'

    def __init__(self, spec):
        ip_string = strip_type_tag(self.type_tag, spec)
        try:
            self.ip = IPAddress(ip_string)
        except AddrFormatError as e:
            raise ValidationError("Invalid IP address: %s." % e)

    def find_subnet(self):
        subnets = list(Subnet.objects.get_subnets_with_ip(self.ip))
        if len(subnets) > 0:
            return subnets[0]
        raise Subnet.DoesNotExist()


class VLANSpecifier(SubnetSpecifier):
    """Identify a subnet by its (nonzero) VLAN tag.

    This only applies to VLANs.  The VLAN tag is a numeric value prefixed with
    a type tag of `vlan:`, e.g. `vlan:12`.  Tags may also be given in
    hexadecimal form: `vlan:0x1a`.  This is case-insensitive.
    """
    type_tag = 'vlan'

    def __init__(self, spec):
        vlan_string = strip_type_tag(self.type_tag, spec)
        if vlan_string.lower().startswith('0x'):
            # Hexadecimal.
            base = 16
        else:
            # Decimal.
            base = 10
        try:
            self.vlan_tag = int(vlan_string, base)
        except ValueError:
            raise ValidationError("Invalid VLAN tag: '%s'." % vlan_string)
        if self.vlan_tag <= 0 or self.vlan_tag >= 0xfff:
            raise ValidationError("VLAN tag out of range (1-4094).")

    def find_subnet(self):
        # The best we can do since we now support a more complex model is
        # get the first VLAN with the VID and the first subnet in that VLAN.
        vlans = VLAN.objects.filter(vid=self.vlan_tag)
        if len(vlans) > 0:
            subnet = vlans[0].subnet_set.first()
            if subnet is not None:
                return subnet
        raise Subnet.DoesNotExist()


SPECIFIER_CLASSES = [NameSpecifier, IPSpecifier, VLANSpecifier]

SPECIFIER_TAGS = {
    spec_class.type_tag: spec_class
    for spec_class in SPECIFIER_CLASSES
}


def get_specifier_type(specifier):
    """Obtain the specifier class that knows how to parse `specifier`.

    :raise ValidationError: If `specifier` does not match any accepted type of
        network specifier.
    :return: A concrete `NetworkSpecifier` subclass that knows how to parse
        `specifier`.
    """
    if ':' in specifier:
        type_tag, _ = specifier.split(':', 1)
    else:
        type_tag = None
    specifier_class = SPECIFIER_TAGS.get(type_tag)
    if specifier_class is None:
        raise ValidationError(
            "Invalid network specifier type: '%s'." % type_tag)
    return specifier_class


def parse_subnet_spec(spec):
    """Parse a network specifier; return it as a `NetworkSpecifier` object.

    :raise ValidationError: If `spec` is malformed.
    """
    specifier_class = get_specifier_type(spec)
    return specifier_class(spec)


def get_subnet_from_spec(spec):
    """Find a single `Subnet` from a given network specifier.

    Note: This exists for a backward compatability layer for how MAAS used to
    do networking. It might not always be correct since the model is now more
    complex, but it will atleast still work.

    :raise ValidationError: If `spec` is malformed.
    :raise Subnet.DoesNotExist: If the subnet specifier does not match
        any known subnet.
    :return: The one `Subnet` matching `spec`.
    """
    specifier = parse_subnet_spec(spec)
    try:
        return specifier.find_subnet()
    except Subnet.DoesNotExist:
        raise Subnet.DoesNotExist("No subnet matching '%s'." % spec)


class AcquireNodeForm(RenamableFieldsForm):
    """A form handling the constraints used to acquire a node."""

    name = forms.CharField(label="Host name", required=False)

    # This becomes a multiple-choice field during cleaning, to accommodate
    # architecture wildcards.
    arch = forms.CharField(label="Architecture", required=False)

    cpu_count = forms.FloatField(
        label="CPU count", required=False,
        error_messages={'invalid': "Invalid CPU count: number required."})

    mem = forms.FloatField(
        label="Memory", required=False,
        error_messages={'invalid': "Invalid memory: number of MiB required."})

    tags = UnconstrainedMultipleChoiceField(label="Tags", required=False)

    not_tags = UnconstrainedMultipleChoiceField(
        label="Not having tags", required=False)

    networks = ValidatorMultipleChoiceField(
        validator=parse_subnet_spec, label="Attached to networks",
        required=False, error_messages={
            'invalid_list': "Invalid parameter: list of networks required.",
            })

    not_networks = ValidatorMultipleChoiceField(
        validator=parse_subnet_spec, label="Not attached to networks",
        required=False, error_messages={
            'invalid_list': "Invalid parameter: list of networks required.",
            })

    connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator, label="Connected to", required=False,
        error_messages={
            'invalid_list':
            "Invalid parameter: list of MAC addresses required."})

    not_connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator, label="Not connected to", required=False,
        error_messages={
            'invalid_list':
            "Invalid parameter: list of MAC addresses required."})

    zone = forms.CharField(label="Physical zone", required=False)

    not_in_zone = ValidatorMultipleChoiceField(
        validator=ZONE_NAME_VALIDATOR, label="Not in zone", required=False,
        error_messages={
            'invalid_list': "Invalid parameter: must list physical zones.",
            })

    storage = forms.CharField(
        validators=[storage_validator], label="Storage", required=False)

    ignore_unknown_constraints = True

    @classmethod
    def Strict(cls, *args, **kwargs):
        """A stricter version of the form which rejects unknown parameters."""
        form = cls(*args, **kwargs)
        form.ignore_unknown_constraints = False
        return form

    def clean_arch(self):
        """Turn `arch` parameter into a list of architecture names.

        Even though `arch` is a single-value field, it turns into a list
        during cleaning.  The architecture parameter may be a wildcard.
        """
        # Import list_all_usable_architectures as part of its module, not
        # directly, so that patch_usable_architectures can easily patch it
        # for testing purposes.
        usable_architectures = maasserver_forms.list_all_usable_architectures()
        architecture_wildcards = get_architecture_wildcards(
            usable_architectures)
        value = self.cleaned_data[self.get_field_name('arch')]
        if value:
            if value in usable_architectures:
                # Full 'arch/subarch' specified directly.
                return [value]
            elif value in architecture_wildcards:
                # Try to expand 'arch' to all available 'arch/subarch'
                # matches.
                return architecture_wildcards[value]
            raise ValidationError(
                {self.get_field_name('arch'):
                    ['Architecture not recognised.']})
        return None

    def clean_tags(self):
        value = self.cleaned_data[self.get_field_name('tags')]
        if value:
            tag_names = parse_legacy_tags(value)
            # Validate tags.
            tag_names = set(tag_names)
            db_tag_names = set(Tag.objects.filter(
                name__in=tag_names).values_list('name', flat=True))
            if len(tag_names) != len(db_tag_names):
                unknown_tags = tag_names.difference(db_tag_names)
                error_msg = 'No such tag(s): %s.' % ', '.join(
                    "'%s'" % tag for tag in unknown_tags)
                raise ValidationError(
                    {self.get_field_name('tags'): [error_msg]})
            return tag_names
        return None

    def clean_zone(self):
        value = self.cleaned_data[self.get_field_name('zone')]
        if value:
            nonexistent_names = detect_nonexistent_zone_names([value])
            if len(nonexistent_names) > 0:
                error_msg = "No such zone: '%s'." % value
                raise ValidationError(
                    {self.get_field_name('zone'): [error_msg]})
            return value
        return None

    def clean_not_in_zone(self):
        value = self.cleaned_data[self.get_field_name('not_in_zone')]
        if value is None or len(value) == 0:
            return None
        nonexistent_names = detect_nonexistent_zone_names(value)
        if len(nonexistent_names) > 0:
            error_msg = "No such zone(s): %s." % ', '.join(nonexistent_names)
            raise ValidationError(
                {self.get_field_name('not_in_zone'): [error_msg]})
        return value

    def clean_networks(self):
        value = self.cleaned_data[self.get_field_name('networks')]
        if value is None:
            return None
        try:
            return [get_subnet_from_spec(spec) for spec in value]
        except Subnet.DoesNotExist as e:
            raise ValidationError(e.message)

    def clean_not_networks(self):
        value = self.cleaned_data[self.get_field_name('not_networks')]
        if value is None:
            return None
        try:
            return [get_subnet_from_spec(spec) for spec in value]
        except Subnet.DoesNotExist as e:
            raise ValidationError(e.message)

    def clean(self):
        if not self.ignore_unknown_constraints:
            unknown_constraints = set(
                self.data).difference(set(self.field_mapping.values()))
            for constraint in unknown_constraints:
                msg = "No such constraint."
                self._errors[constraint] = self.error_class([msg])
        return super(AcquireNodeForm, self).clean()

    def describe_constraint(self, field_name):
        """Return a human-readable representation of a constraint.

        Turns a constraint value as passed to the form into a Juju-like
        representation for display: `name=foo`.  Multi-valued constraints are
        shown as comma-separated values, e.g. `tags=do,re,mi`.

        :param field_name: Name of the constraint on this form, e.g. `zone`.
        :return: A constraint string, or `None` if the constraint is not set.
        """
        value = self.cleaned_data[field_name]
        if isinstance(self.fields[field_name], MultipleChoiceField):
            output = describe_multi_constraint_value(value)
        elif field_name == 'arch' and not isinstance(value, (bytes, unicode)):
            # The arch field is a special case.  It's defined as a string
            # field, but may become a list/tuple/... of strings in cleaning.
            output = describe_multi_constraint_value(value)
        else:
            output = describe_single_constraint_value(value)
        if output is None:
            return None
        else:
            return '%s=%s' % (field_name, output)

    def describe_constraints(self):
        """Return a human-readable representation of the given constraints.

        The description is Juju-like, e.g. `arch=amd64 cpu=16 zone=rack3`.
        Constraints are listed in alphabetical order.
        """
        constraints = (
            self.describe_constraint(name)
            for name in sorted(self.fields.keys())
            )
        return ' '.join(
            constraint
            for constraint in constraints
            if constraint is not None)

    def filter_nodes(self, nodes):
        """Return the subset of nodes that match the form's constraints.

        :param nodes:  The set of nodes on which the form should apply
            constraints.
        :type nodes: `django.db.models.query.QuerySet`
        :return: A QuerySet of the nodes that match the form's constraints.
        :rtype: `django.db.models.query.QuerySet`
        """
        filtered_nodes = nodes

        # Filter by hostname.
        hostname = self.cleaned_data.get(self.get_field_name('name'))
        if hostname:
            clause = Q(hostname=hostname)
            # If the given hostname has a domain part, try matching
            # against the nodes' FQDNs as well (the FQDN is built using
            # the nodegroup's name as the domain name).
            if "." in hostname:
                host, domain = hostname.split('.', 1)
                hostname_clause = (
                    Q(hostname__startswith="%s." % host) |
                    Q(hostname=host)
                )
                domain_clause = Q(nodegroup__name=domain)
                clause = clause | (hostname_clause & domain_clause)
            filtered_nodes = filtered_nodes.filter(clause)

        # Filter by architecture.
        arch = self.cleaned_data.get(self.get_field_name('arch'))
        if arch:
            filtered_nodes = filtered_nodes.filter(architecture__in=arch)

        # Filter by cpu_count.
        cpu_count = self.cleaned_data.get(self.get_field_name('cpu_count'))
        if cpu_count:
            filtered_nodes = filtered_nodes.filter(cpu_count__gte=cpu_count)

        # Filter by memory.
        mem = self.cleaned_data.get(self.get_field_name('mem'))
        if mem:
            filtered_nodes = filtered_nodes.filter(memory__gte=mem)

        # Filter by tags.
        tags = self.cleaned_data.get(self.get_field_name('tags'))
        if tags:
            for tag in tags:
                filtered_nodes = filtered_nodes.filter(tags__name=tag)

        # Filter by not_tags.
        not_tags = self.cleaned_data.get(self.get_field_name('not_tags'))
        if len(not_tags) > 0:
            for not_tag in not_tags:
                filtered_nodes = filtered_nodes.exclude(tags__name=not_tag)

        # Filter by zone.
        zone = self.cleaned_data.get(self.get_field_name('zone'))
        if zone:
            zone_obj = Zone.objects.get(name=zone)
            filtered_nodes = filtered_nodes.filter(zone=zone_obj)

        # Filter by not_in_zone.
        not_in_zone = self.cleaned_data.get(self.get_field_name('not_in_zone'))
        if not_in_zone is not None and len(not_in_zone) > 0:
            not_in_zones = Zone.objects.filter(name__in=not_in_zone)
            filtered_nodes = filtered_nodes.exclude(zone__in=not_in_zones)

        # Filter by networks.
        subnets = self.cleaned_data.get(self.get_field_name('networks'))
        if subnets is not None:
            for subnet in set(subnets):
                filtered_nodes = filtered_nodes.filter(
                    interface__ip_addresses__subnet=subnet)

        # Filter by not_networks.
        not_subnets = self.cleaned_data.get(
            self.get_field_name('not_networks'))
        if not_subnets is not None:
            for not_subnet in set(not_subnets):
                filtered_nodes = filtered_nodes.exclude(
                    interface__ip_addresses__subnet=not_subnet)

        # Filter by connected_to.
        connected_to = self.cleaned_data.get(
            self.get_field_name('connected_to'))
        if connected_to:
            where, params = macs_contain(
                "routers", connected_to)
            filtered_nodes = filtered_nodes.extra(
                where=[where], params=params)

        # Filter by not_connected_to.
        not_connected_to = self.cleaned_data.get(
            self.get_field_name('not_connected_to'))
        if not_connected_to:
            where, params = macs_do_not_contain(
                "routers", not_connected_to)
            filtered_nodes = filtered_nodes.extra(
                where=[where], params=params)

        # Filter by storage.
        compatible_nodes = {}  # Maps node/storage to named storage constraints
        storage = self.cleaned_data.get(
            self.get_field_name('storage'))
        if storage:
            compatible_nodes = nodes_by_storage(storage)
            node_ids = compatible_nodes.keys()
            if node_ids is not None:
                filtered_nodes = filtered_nodes.filter(id__in=node_ids)

        # This uses a very simple procedure to compute a machine's
        # cost. This procedure is loosely based on how ec2 computes
        # the costs of machines. This is here to give a hint to let
        # the call to acquire() decide which machine to return based
        # on the machine's cost when multiple machines match the
        # constraints.
        filtered_nodes = filtered_nodes.distinct().extra(
            select={'cost': "cpu_count + memory / 1024"})
        return filtered_nodes.order_by("cost"), compatible_nodes
