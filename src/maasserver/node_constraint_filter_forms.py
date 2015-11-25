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


from collections import defaultdict
import itertools
from itertools import chain
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.fields import Field
from maasserver.fields import mac_validator
from maasserver.forms import (
    MultipleChoiceField,
    UnconstrainedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
import maasserver.forms as maasserver_forms
from maasserver.models import (
    Interface,
    PhysicalBlockDevice,
    Subnet,
    Tag,
    Zone,
)
from maasserver.models.zone import ZONE_NAME_VALIDATOR
from maasserver.utils.forms import set_form_error
from maasserver.utils.orm import (
    macs_contain,
    macs_do_not_contain,
)
from provisioningserver.utils.constraints import LabeledConstraintMap

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

NETWORKING_CONSTRAINT_NAMES = {
    'space',
    'not_space',
    'fabric_class',
    'not_fabric_class',
    'subnet_cidr',
    'not_subnet_cidr',
    'vid',
    'not_vid',
    'fabric',
    'not_fabric',
    'subnet',
    'not_subnet',
    'mode',
}


def interfaces_validator(constraint_map):
    """Validate the given LabeledConstraintMap object."""
    # At this point, the basic syntax of a labeled constraint map will have
    # already been validated by the underlying form field. However, we also
    # need to validate the specified things we're looking for in the
    # interfaces domain.
    for label in constraint_map:
        constraints = constraint_map[label]
        for constraint_name in constraints.iterkeys():
            if constraint_name not in NETWORKING_CONSTRAINT_NAMES:
                raise ValidationError(
                    "Unknown interfaces constraint: '%s" % constraint_name)


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


def nodes_by_interface(interfaces_label_map):
    """Determines the set of nodes that match the specified
    LabeledConstraintMap (which must be a map of interface constraints.)

    Returns a dictionary in the format:
    {
        <label1>: {
            <node1>: [<interface1>, <interface2>, ...]
            <node2>: ...
            ...
        }
        <label2>: ...
    }

    :param interfaces_label_map: LabeledConstraintMap
    :return: dict
    """
    node_ids = None
    label_map = {}
    for label in interfaces_label_map:
        constraints = interfaces_label_map[label]
        if node_ids is None:
            # The first time through the filter, build the list
            # of candidate nodes.
            node_ids, node_map = Interface.objects.get_matching_node_map(
                constraints)
            label_map[label] = node_map
        else:
            # For subsequent labels, only match nodes that already matched a
            # preceding label. Use the set intersection operator to do this,
            # because that will yield more complete data in the label_map.
            # (which is less efficient, but may be needed for troubleshooting.)
            # If a more efficient approach is desired, this could be changed
            # to filter the nodes starting from an 'id__in' filter using the
            # current 'node_ids' set.
            new_node_ids, node_map = Interface.objects.get_matching_node_map(
                constraints)
            label_map[label] = node_map
            node_ids &= new_node_ids
    return node_ids, label_map


class LabeledConstraintMapField(Field):

    def __init__(self, *args, **kwargs):
        super(LabeledConstraintMapField, self).__init__(*args, **kwargs)
        self.validators.insert(
            0, lambda constraint_map: constraint_map.validate(
                exception_type=ValidationError))

    def to_python(self, value):
        """Returns a LabeledConstraintMap object."""
        if value is not None and len(value.strip()) != 0:
            return LabeledConstraintMap(value)


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

    # XXX mpontillo 2015-10-30 need validators for fabric constraints
    fabrics = ValidatorMultipleChoiceField(
        validator=lambda x: True, label="Attached to fabrics",
        required=False, error_messages={
            'invalid_list': "Invalid parameter: list of fabrics required.",
            })

    not_fabrics = ValidatorMultipleChoiceField(
        validator=lambda x: True, label="Not attached to fabrics",
        required=False, error_messages={
            'invalid_list': "Invalid parameter: list of fabrics required.",
            })

    fabric_classes = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Attached to fabric with specified classes",
        required=False, error_messages={
            'invalid_list':
            "Invalid parameter: list of fabric classes required.",
        })

    not_fabric_classes = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Not attached to fabric with specified classes",
        required=False, error_messages={
            'invalid_list':
            "Invalid parameter: list of fabric classes required."
        })

    networks = ValidatorMultipleChoiceField(
        validator=Subnet.objects.validate_filter_specifiers,
        label="Attached to subnets",
        required=False, error_messages={
            'invalid_list':
            "Invalid parameter: list of subnet specifiers required.",
            })

    not_networks = ValidatorMultipleChoiceField(
        validator=Subnet.objects.validate_filter_specifiers,
        label="Not attached to subnets",
        required=False, error_messages={
            'invalid_list':
            "Invalid parameter: list of subnet specifiers required.",
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

    interfaces = LabeledConstraintMapField(
        validators=[interfaces_validator], label="Interfaces", required=False)

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
            set_form_error(
                self, self.get_field_name('arch'),
                'Architecture not recognised.')
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
                set_form_error(self, self.get_field_name('tags'), error_msg)
                return None
            return tag_names
        return None

    def clean_zone(self):
        value = self.cleaned_data[self.get_field_name('zone')]
        if value:
            nonexistent_names = detect_nonexistent_zone_names([value])
            if len(nonexistent_names) > 0:
                error_msg = "No such zone: '%s'." % value
                set_form_error(self, self.get_field_name('zone'), error_msg)
                return None
            return value
        return None

    def clean_not_in_zone(self):
        value = self.cleaned_data[self.get_field_name('not_in_zone')]
        if value is None or len(value) == 0:
            return None
        nonexistent_names = detect_nonexistent_zone_names(value)
        if len(nonexistent_names) > 0:
            error_msg = "No such zone(s): %s." % ', '.join(nonexistent_names)
            set_form_error(self, self.get_field_name('not_in_zone'), error_msg)
            return None
        return value

    def _clean_subnet_specifiers(self, specifiers):
        if not specifiers:
            return None
        subnets = set(Subnet.objects.filter_by_specifiers(specifiers))
        if len(subnets) == 0:
            raise ValidationError("No matching subnets found.")
        return subnets

    def clean_networks(self):
        value = self.cleaned_data[self.get_field_name('networks')]
        return self._clean_subnet_specifiers(value)

    def clean_not_networks(self):
        value = self.cleaned_data[self.get_field_name('not_networks')]
        return self._clean_subnet_specifiers(value)

    def __init__(self, *args, **kwargs):
        super(AcquireNodeForm, self).__init__(*args, **kwargs)

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

        # Filter by subnet.
        subnets = self.cleaned_data.get(self.get_field_name('networks'))
        if subnets is not None and len(subnets) > 0:
            for subnet in set(subnets):
                filtered_nodes = filtered_nodes.filter(
                    interface__ip_addresses__subnet=subnet)

        # Filter by not_subnets.
        not_subnets = self.cleaned_data.get(
            self.get_field_name('not_networks'))
        if not_subnets is not None and len(not_subnets) > 0:
            for not_subnet in set(not_subnets):
                filtered_nodes = filtered_nodes.exclude(
                    interface__ip_addresses__subnet=not_subnet)

        # Filter by fabrics.
        fabrics = self.cleaned_data.get(self.get_field_name('fabrics'))
        if fabrics is not None and len(fabrics) > 0:
            # XXX mpontillo 2015-10-30 need to also handle fabrics whose name
            # is null (fabric-<id>).
            filtered_nodes = filtered_nodes.filter(
                interface__vlan__fabric__name__in=fabrics)

        # Filter by not_fabrics.
        not_fabrics = self.cleaned_data.get(self.get_field_name('not_fabrics'))
        if not_fabrics is not None and len(not_fabrics) > 0:
            # XXX mpontillo 2015-10-30 need to also handle fabrics whose name
            # is null (fabric-<id>).
            filtered_nodes = filtered_nodes.exclude(
                interface__vlan__fabric__name__in=not_fabrics)

        # Filter by fabric classes.
        fabric_classes = self.cleaned_data.get(self.get_field_name(
            'fabric_classes'))
        if fabric_classes is not None and len(fabric_classes) > 0:
            filtered_nodes = filtered_nodes.filter(
                interface__vlan__fabric__class_type__in=fabric_classes)

        # Filter by not_fabric_classes.
        not_fabric_classes = self.cleaned_data.get(self.get_field_name(
            'not_fabric_classes'))
        if not_fabric_classes is not None and len(not_fabric_classes) > 0:
            filtered_nodes = filtered_nodes.exclude(
                interface__vlan__fabric__class_type__in=not_fabric_classes)

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

        # Filter by interfaces (networking)
        compatible_interfaces = {}
        interfaces_label_map = self.cleaned_data.get(
            self.get_field_name('interfaces'))
        if interfaces_label_map is not None:
            node_ids, compatible_interfaces = nodes_by_interface(
                interfaces_label_map)
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
        return (
            filtered_nodes.order_by("cost"), compatible_nodes,
            compatible_interfaces
        )
