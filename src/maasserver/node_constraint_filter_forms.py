# Copyright 2013-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import defaultdict
import itertools
from itertools import chain
import re

import attr
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Model, Q
from django.forms.fields import Field
from netaddr import IPAddress

from maasserver.enum import NODE_STATUS, NODE_STATUS_SHORT_LABEL_CHOICES
from maasserver.fields import mac_validator, MODEL_NAME_VALIDATOR
import maasserver.forms as maasserver_forms
from maasserver.forms import (
    MultipleChoiceField,
    UnconstrainedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
from maasserver.models import (
    BlockDevice,
    Filesystem,
    Interface,
    Node,
    Partition,
    Pod,
    ResourcePool,
    Subnet,
    Tag,
    VLAN,
    Zone,
)
from maasserver.models.nodeconfig import NODE_CONFIG_DEFAULT
from maasserver.utils.forms import set_form_error
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
    r"(?P<size>[0-9.]+)"  # Mandatory size
    r"(?:\((?P<tags>[^)]+)\))?",  # Optional tag list between parentheses
    re.VERBOSE,
)


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
            group = name + ":"  # start with the constraint name
        group += size  # add the size part
        if tags != "":
            group += "(%s)" % tags  # add the tags, if present
        rendered_groups.append(group)
    if ",".join(rendered_groups) != value:
        raise ValidationError('Malformed storage constraint, "%s".' % value)


NETWORKING_CONSTRAINT_NAMES = {
    "id",
    "not_id",
    "fabric",
    "not_fabric",
    "fabric_class",
    "not_fabric_class",
    "ip",
    "not_ip",
    "mode",
    "name",
    "not_name",
    "hostname",
    "not_hostname",
    "subnet",
    "not_subnet",
    "space",
    "not_space",
    "subnet_cidr",
    "not_subnet_cidr",
    "type",
    "vlan",
    "not_vlan",
    "vid",
    "not_vid",
    "tag",
    "not_tag",
    "link_speed",
}


DEVICE_CONSTRAINT_NAMES = {
    "vendor_id",
    "product_id",
    "vendor_name",
    "product_name",
    "commissioning_driver",
}


IGNORED_FIELDS = {
    "comment",
    "bridge_all",
    "bridge_type",
    "bridge_stp",
    "bridge_fd",
    "dry_run",
    "verbose",
    "op",
    "agent_name",
}


@attr.s
class NodesByInterfaceResult:
    """Return value for `nodes_by_interface()` function."""

    # List of node IDs that match the constraints.
    node_ids = attr.ib()

    # Dictionary that maps interface labels to matching interfaces.
    label_map = attr.ib()

    # Dictionary of IP address allocations by label.
    allocated_ips = attr.ib(default=None)

    # Dictionary of IP modes by label
    ip_modes = attr.ib(default=None)


def interfaces_validator(constraint_map):
    """Validate the given LabeledConstraintMap object."""
    # At this point, the basic syntax of a labeled constraint map will have
    # already been validated by the underlying form field. However, we also
    # need to validate the specified things we're looking for in the
    # interfaces domain.
    for label in constraint_map:
        constraints = constraint_map[label]
        for constraint_name in constraints:
            if constraint_name not in NETWORKING_CONSTRAINT_NAMES:
                raise ValidationError(
                    "Unknown interfaces constraint: '%s" % constraint_name
                )


def devices_validator(values):
    for value in values.split(","):
        key = value.split("=", 1)[0]
        if key not in DEVICE_CONSTRAINT_NAMES:
            raise ValidationError("Unknown devices constraint: '%s" % key)


def generate_architecture_wildcards(arches):
    """Map 'primary' architecture names to a list of full expansions.

    Return a dictionary keyed by the primary architecture name (the part before
    the '/'). The value of an entry is a frozenset of full architecture names
    ('primary_arch/subarch') under the keyed primary architecture.
    """
    sorted_arch_list = sorted(arches)

    def extract_primary_arch(arch):
        return arch.split("/")[0]

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
    if "armhf" in wildcards and "arm" not in wildcards:
        wildcards["arm"] = wildcards["armhf"]
    return wildcards


def parse_legacy_tags(values):
    # Support old-method to pass a list of strings using a
    # comma-separated or space-separated list.
    # 'values' is assumed to be a list of strings.
    result = chain.from_iterable(
        re.findall(r"[^\s,]+", value) for value in values
    )
    return list(result)


# Mapping used to rename the fields from the FilterNodeForm form.
# The new names correspond to the names used by Juju.  This is used so
# that the search form present on the node listing page can be used to
# filter nodes using Juju's semantics.
JUJU_ACQUIRE_FORM_FIELDS_MAPPING = {
    "name": "maas-name",
    "tags": "maas-tags",
    "arch": "architecture",
    "cpu_count": "cpu",
    "storage": "storage",
}


# XXX JeroenVermeulen 2014-02-06: Can we document this please?
class RenamableFieldsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


def detect_nonexistent_names(model_class, names):
    """Check for, and return, names of nonexistent objects.

    Used for checking object names as passed to the `FilterNodeForm`.

    :param model_class: A model class that has a name attribute.
    :param names: List, tuple, or set of purpoprted zone names.
    :return: A sorted list of those names that did not name existing zones.
    """
    assert isinstance(names, (list, tuple, set))
    if len(names) == 0:
        return []
    existing_names = set(
        model_class.objects.all().values_list("name", flat=True)
    )
    return sorted(set(names) - existing_names)


def describe_single_constraint_value(value):
    """Return an atomic constraint value as human-readable text.

    :param value: Simple form value for some constraint.
    :return: String representation of `value`, or `None` if the value
        means that the constraint was not set.
    """
    if value is None or value == "":
        return None
    else:
        return "%s" % value


def describe_multi_constraint_value(values):
    """Return a multi-valued constraint value as human-readable text.

    :param values: Sequence form value for some constraint.
    :return: String representation of `value`, or `None` if the value
        means that the constraint was not set.
    """
    if values is None or len(values) == 0:
        return None
    else:
        if isinstance(values, (set, dict, frozenset)):
            # Order unordered containers for consistency.
            sequence = sorted(
                value.pk if isinstance(value, Model) else value
                for value in values
            )
        else:
            # Keep ordered containers in their original order.
            sequence = values
        return ",".join(map(describe_single_constraint_value, sequence))


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
            int(float(size) * (1000**3)),
            tags.split(",") if tags != "" else None,
        )
        for (label, size, tags) in groups
    ]

    def count_tags(elem):
        label, size, tags = elem
        return 0 if tags is None else len(tags)

    head, tail = constraints[:1], constraints[1:]
    tail.sort(key=count_tags, reverse=True)
    return head + tail


def format_device_key(device_info):
    """Format the `device_info` into a key for the storage constraint output."""
    device_type, device_id = device_info
    if device_type == "blockdev":
        return device_id
    elif device_type == "partition":
        return "partition:%d" % device_id
    else:
        raise ValueError("Unknown device_type: %s" % device_type)


def nodes_by_storage(storage, node_ids=None):
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
    if node_ids:
        node_config_ids = Node.objects.filter(id__in=node_ids).values_list(
            "current_config_id", flat=True
        )
    else:
        node_config_ids = []
    for constraint_name, size, tags in constraints:
        if root_device:
            # This branch of the if is only used on first iteration.
            root_device = False
            part_match = False

            # Use only block devices that are mounted as '/'. Either the
            # block device has root sitting on it or its on a partition on
            # that block device.
            filesystems = Filesystem.objects.filter(
                mount_point="/", acquired=False
            )
            if tags is not None and "partition" in tags:
                part_match = True
                part_tags = list(tags)
                part_tags.remove("partition")
                filesystems = filesystems.filter(partition__size__gte=size)
                if part_tags:
                    filesystems = filesystems.filter(
                        partition__tags__contains=part_tags
                    )
                if node_config_ids:
                    filesystems = filesystems.filter(
                        Q(
                            **{
                                "partition__partition_table__block_device"
                                "__node_config_id__in": node_config_ids,
                            }
                        )
                    )
            else:
                filesystems = filesystems.filter(
                    Q(block_device__size__gte=size)
                    | Q(
                        **{
                            "partition__partition_table__block_device"
                            "__size__gte": size
                        }
                    )
                )
                if tags:
                    filesystems = filesystems.filter(
                        Q(block_device__tags__contains=tags)
                        | Q(
                            **{
                                "partition__partition_table__block_device"
                                "__tags__contains": tags
                            }
                        )
                    )
                if node_config_ids:
                    filesystems = filesystems.filter(
                        Q(block_device__node_config_id__in=node_config_ids)
                        | Q(
                            **{
                                "partition__partition_table__block_device"
                                "__node_config_id__in": node_config_ids
                            }
                        )
                    )
            filesystems = filesystems.prefetch_related(
                "block_device", "partition__partition_table__block_device"
            )

            # Only keep the first device for every node. This is done to make
            # sure filtering out the size and tags is not done to all the
            # block devices. This should only be done to the first block
            # device.
            found_nodes = set()
            matched_devices = []
            for filesystem in filesystems:
                if part_match:
                    device = filesystem.partition
                    node_id = (
                        device.partition_table.block_device.node_config.node_id
                    )
                elif filesystem.block_device is not None:
                    device = filesystem.block_device
                    node_id = device.node_config.node_id
                else:
                    device = filesystem.partition.partition_table.block_device
                    node_id = device.node_config.node_id
                if node_id in found_nodes:
                    continue
                matched_devices.append(device)
                found_nodes.add(node_id)
        elif tags is not None and "partition" in tags:
            # Query for any partition the closest size and the given tags.
            # The partition must also be unused in the storage model.
            part_tags = list(tags)
            part_tags.remove("partition")
            matched_devices = Partition.objects.filter(size__gte=size)
            matched_devices = matched_devices.filter(filesystem__isnull=True)
            if part_tags:
                matched_devices = matched_devices.filter(
                    tags__contains=part_tags
                )
            if node_config_ids:
                matched_devices = matched_devices.filter(
                    partition_table__block_device__node_config_id__in=node_config_ids
                )
            matched_devices = list(matched_devices.order_by("size"))
        else:
            # Query for any block device the closest size and, if specified,
            # the given tags. # The block device must also be unused in the
            # storage model.
            matched_devices = BlockDevice.objects.filter(
                node_config__name=NODE_CONFIG_DEFAULT, size__gte=size
            )
            matched_devices = matched_devices.filter(
                filesystem__isnull=True, partitiontable__isnull=True
            )
            if tags is not None:
                matched_devices = matched_devices.filter(tags__contains=tags)
            if node_config_ids:
                matched_devices = matched_devices.filter(
                    node_config_id__in=node_config_ids
                )
            matched_devices = list(matched_devices.order_by("size"))

        # Loop through all the returned devices. Insert only the first
        # device from each node into `matches`.
        matched_in_loop = []
        for device in matched_devices:
            device_id = device.id
            if isinstance(device, Partition):
                device_type = "partition"
                device_node_id = (
                    device.partition_table.block_device.node_config.node_id
                )
            elif isinstance(device, BlockDevice):
                device_type = "blockdev"
                device_node_id = device.node_config.node_id
            else:
                raise TypeError(
                    "Unknown device type: %s" % type(device).__name__
                )

            if device_node_id in matched_in_loop:
                continue
            if (device_type, device_id) in matches[device_node_id]:
                continue
            matches[device_node_id][(device_type, device_id)] = constraint_name
            matched_in_loop.append(device_node_id)

    # Return only the nodes that have the correct number of disks.
    nodes = {
        node_id: {
            format_device_key(device_info): name
            for device_info, name in disks.items()
            if name != ""  # Map only those w/ named constraints
        }
        for node_id, disks in matches.items()
        if len(disks) == len(constraints)
    }
    return nodes


def nodes_by_interface(
    interfaces_label_map, include_filter=None, preconfigured=True
):
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
    :param include_filter: A dictionary suitable for passing into the Django
        QuerySet filter() arguments, representing the set of initial interfaces
        to filter.
    :param preconfigured: If True, assumes that the specified constraint values
        have already been configured. If False, also considers nodes whose
        VLANs (but not necessarily subnets or IP addresses) match, so that
        the node can be configured per the constraints post-allocation.
    :return: NodesByInterfaceResult object
    """
    node_ids = None
    label_map = {}
    allocated_ips = {}
    ip_modes = {}
    for label in interfaces_label_map:
        constraints = interfaces_label_map[label]
        if not preconfigured:
            # This code path is used for pods, where the machine doesn't yet
            # exist, but will be created based on the constraints.
            if "ip" in constraints:
                vlan_constraints = constraints.pop("vlan", [])
                ip_constraints = constraints.pop("ip")
                for ip in ip_constraints:
                    allocations_by_label = allocated_ips.pop(label, [])
                    allocations_by_label.append(str(IPAddress(ip)))
                    allocated_ips[label] = allocations_by_label
                    subnet = Subnet.objects.get_best_subnet_for_ip(ip)
                    # Convert the specified IP address constraint into a VLAN
                    # constraint. At this point, we don't care if the IP
                    # address matches. We only care that we have allocated
                    # an IP address on a VLAN that will exist on the composed
                    # machine.
                    vlan_constraints.append("id:%d" % subnet.vlan.id)
                constraints["vlan"] = vlan_constraints
            if "mode" in constraints:
                mode_constraints = constraints.pop("mode")
                for mode in mode_constraints:
                    # This will be used later when a subnet is selected.
                    ip_modes[label] = mode
        if node_ids is None:
            # The first time through the filter, build the list
            # of candidate nodes.
            node_ids, node_map = Interface.objects.get_matching_node_map(
                constraints, include_filter=include_filter
            )
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
                constraints, include_filter=include_filter
            )
            label_map[label] = node_map
            node_ids &= new_node_ids
    return NodesByInterfaceResult(
        node_ids=node_ids,
        label_map=label_map,
        allocated_ips=allocated_ips,
        ip_modes=ip_modes,
    )


class LabeledConstraintMapField(Field):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validators.insert(
            0,
            lambda constraint_map: constraint_map.validate(
                exception_type=ValidationError
            ),
        )

    def to_python(self, value):
        """Returns a LabeledConstraintMap object."""
        if isinstance(value, LabeledConstraintMap):
            return value
        elif value is not None and len(value.strip()) != 0:
            return LabeledConstraintMap(value)


class FilterNodeForm(RenamableFieldsForm):
    """A form for filtering nodes."""

    # This becomes a multiple-choice field during cleaning, to accommodate
    # architecture wildcards.
    arch = forms.CharField(label="Architecture", required=False)

    tags = UnconstrainedMultipleChoiceField(label="Tags", required=False)

    not_tags = UnconstrainedMultipleChoiceField(
        label="Not having tags", required=False
    )

    # XXX mpontillo 2015-10-30 need validators for fabric constraints
    fabrics = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Attached to fabrics",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of fabrics required."
        },
    )

    not_fabrics = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Not attached to fabrics",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of fabrics required."
        },
    )

    fabric_classes = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Attached to fabric with specified classes",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of fabric classes required."
        },
    )

    not_fabric_classes = ValidatorMultipleChoiceField(
        validator=lambda x: True,
        label="Not attached to fabric with specified classes",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of fabric classes required."
        },
    )

    subnets = ValidatorMultipleChoiceField(
        validator=Subnet.objects.validate_filter_specifiers,
        label="Attached to subnets",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of subnet specifiers required."
        },
    )

    not_subnets = ValidatorMultipleChoiceField(
        validator=Subnet.objects.validate_filter_specifiers,
        label="Not attached to subnets",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of subnet specifiers required."
        },
    )

    link_speed = forms.FloatField(
        label="Link speed",
        required=False,
        error_messages={"invalid": "Invalid link speed: number required."},
    )

    vlans = ValidatorMultipleChoiceField(
        validator=VLAN.objects.validate_filter_specifiers,
        label="Attached to VLANs",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of VLAN specifiers required."
        },
    )

    not_vlans = ValidatorMultipleChoiceField(
        validator=VLAN.objects.validate_filter_specifiers,
        label="Not attached to VLANs",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of VLAN specifiers required."
        },
    )

    connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator,
        label="Connected to",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of MAC addresses required."
        },
    )

    not_connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator,
        label="Not connected to",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: list of MAC addresses required."
        },
    )

    zone = forms.CharField(label="Physical zone", required=False)

    not_in_zone = ValidatorMultipleChoiceField(
        validator=MODEL_NAME_VALIDATOR,
        label="Not in zone",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: must list physical zones."
        },
    )

    pool = forms.CharField(label="Resource pool", required=False)

    not_in_pool = ValidatorMultipleChoiceField(
        validator=MODEL_NAME_VALIDATOR,
        label="Not in resource pool",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: must list resource pools."
        },
    )

    storage = forms.CharField(
        validators=[storage_validator], label="Storage", required=False
    )

    interfaces = LabeledConstraintMapField(
        validators=[interfaces_validator], label="Interfaces", required=False
    )

    devices = forms.CharField(
        validators=[devices_validator], label="Devices", required=False
    )

    cpu_count = forms.FloatField(
        label="CPU count",
        required=False,
        error_messages={"invalid": "Invalid CPU count: number required."},
    )

    mem = forms.FloatField(
        label="Memory",
        required=False,
        error_messages={"invalid": "Invalid memory: number of MiB required."},
    )

    pod = forms.CharField(label="The name of the desired pod", required=False)

    not_pod = forms.CharField(
        label="The name of the undesired pod", required=False
    )

    pod_type = forms.CharField(
        label="The power_type of the desired pod", required=False
    )

    not_pod_type = forms.CharField(
        label="The power_type of the undesired pod", required=False
    )

    ignore_unknown_constraints = False

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
            usable_architectures
        )
        value = self.cleaned_data[self.get_field_name("arch")]
        if value:
            if value in usable_architectures:
                # Full 'arch/subarch' specified directly.
                return [value]
            elif value in architecture_wildcards:
                # Try to expand 'arch' to all available 'arch/subarch'
                # matches.
                return architecture_wildcards[value]
            set_form_error(
                self,
                self.get_field_name("arch"),
                "Architecture not recognised.",
            )
        return None

    def clean_tags(self):
        value = self.cleaned_data[self.get_field_name("tags")]
        if value:
            tag_names = parse_legacy_tags(value)
            # Validate tags.
            tag_names = set(tag_names)
            db_tag_names = set(
                Tag.objects.filter(name__in=tag_names).values_list(
                    "name", flat=True
                )
            )
            if len(tag_names) != len(db_tag_names):
                unknown_tags = tag_names.difference(db_tag_names)
                error_msg = "No such tag(s): %s." % ", ".join(
                    "'%s'" % tag for tag in unknown_tags
                )
                set_form_error(self, self.get_field_name("tags"), error_msg)
                return None
            return tag_names
        return None

    def clean_zone(self):
        value = self.cleaned_data[self.get_field_name("zone")]
        if value:
            nonexistent_names = detect_nonexistent_names(Zone, [value])
            if nonexistent_names:
                error_msg = "No such zone: '%s'." % value
                set_form_error(self, self.get_field_name("zone"), error_msg)
                return None
            return value
        return None

    def clean_not_in_zone(self):
        value = self.cleaned_data[self.get_field_name("not_in_zone")]
        if not value:
            return None
        nonexistent_names = detect_nonexistent_names(Zone, value)
        if nonexistent_names:
            error_msg = "No such zone(s): %s." % ", ".join(nonexistent_names)
            set_form_error(self, self.get_field_name("not_in_zone"), error_msg)
            return None
        return value

    def clean_pool(self):
        value = self.cleaned_data[self.get_field_name("pool")]
        if value:
            nonexistent_names = detect_nonexistent_names(ResourcePool, [value])
            if nonexistent_names:
                error_msg = "No such pool: '%s'." % value
                set_form_error(self, self.get_field_name("pool"), error_msg)
                return None
            return value
        return None

    def clean_not_in_pool(self):
        value = self.cleaned_data[self.get_field_name("not_in_pool")]
        if not value:
            return None
        nonexistent_names = detect_nonexistent_names(ResourcePool, value)
        if nonexistent_names:
            error_msg = "No such pool(s): %s." % ", ".join(nonexistent_names)
            set_form_error(self, self.get_field_name("not_in_pool"), error_msg)
            return None
        return value

    def _clean_specifiers(self, model, specifiers):
        if not specifiers:
            return None
        objects = set(model.objects.filter_by_specifiers(specifiers))
        if len(objects) == 0:
            raise ValidationError(
                "No matching %s found." % model._meta.verbose_name_plural
            )
        return objects

    def clean_subnets(self):
        value = self.cleaned_data[self.get_field_name("subnets")]
        return self._clean_specifiers(Subnet, value)

    def clean_not_subnets(self):
        value = self.cleaned_data[self.get_field_name("not_subnets")]
        return self._clean_specifiers(Subnet, value)

    def clean_vlans(self):
        value = self.cleaned_data[self.get_field_name("vlans")]
        return self._clean_specifiers(VLAN, value)

    def clean_not_vlans(self):
        value = self.cleaned_data[self.get_field_name("not_vlans")]
        return self._clean_specifiers(VLAN, value)

    def clean(self):
        if not self.ignore_unknown_constraints:
            unknown_constraints = set(self.data).difference(
                set(self.field_mapping.values())
            )
            for constraint in unknown_constraints:
                if constraint not in IGNORED_FIELDS:
                    msg = "No such constraint."
                    self._errors[constraint] = self.error_class([msg])
        return super().clean()

    def describe_constraint(self, field_name):
        """Return a human-readable representation of a constraint.

        Turns a constraint value as passed to the form into a Juju-like
        representation for display: `name=foo`.  Multi-valued constraints are
        shown as comma-separated values, e.g. `tags=do,re,mi`.

        :param field_name: Name of the constraint on this form, e.g. `zone`.
        :return: A constraint string, or `None` if the constraint is not set.
        """
        value = self.cleaned_data.get(field_name, None)
        if value is None:
            return None
        if isinstance(self.fields[field_name], MultipleChoiceField):
            output = describe_multi_constraint_value(value)
        elif field_name == "arch" and not isinstance(value, str):
            # The arch field is a special case.  It's defined as a string
            # field, but may become a list/tuple/... of strings in cleaning.
            output = describe_multi_constraint_value(value)
        else:
            output = describe_single_constraint_value(value)
        if output is None:
            return None
        else:
            return f"{field_name}={output}"

    def describe_constraints(self):
        """Return a human-readable representation of the given constraints.

        The description is Juju-like, e.g. `arch=amd64 cpu=16 zone=rack3`.
        Constraints are listed in alphabetical order.
        """
        constraints = (
            self.describe_constraint(name)
            for name in sorted(self.fields.keys())
        )
        return " ".join(
            constraint for constraint in constraints if constraint is not None
        )

    def filter_nodes(self, nodes):
        """Return the subset of nodes that match the form's constraints.

        :param nodes:  The set of nodes on which the form should apply
            constraints.
        :type nodes: `django.db.models.query.QuerySet`
        :return: A QuerySet of the nodes that match the form's constraints.
        :rtype: `django.db.models.query.QuerySet`
        """
        filtered_nodes = self._apply_filters(nodes)
        compatible_nodes, filtered_nodes = self.filter_by_storage(
            filtered_nodes
        )
        compatible_interfaces, filtered_nodes = self.filter_by_interfaces(
            filtered_nodes
        )
        return filtered_nodes, compatible_nodes, compatible_interfaces

    def _apply_filters(self, nodes):
        nodes = self.filter_by_arch(nodes)
        nodes = self.filter_by_tags(nodes)
        nodes = self.filter_by_zone(nodes)
        nodes = self.filter_by_pool(nodes)
        nodes = self.filter_by_subnets(nodes)
        nodes = self.filter_by_link_speed(nodes)
        nodes = self.filter_by_vlans(nodes)
        nodes = self.filter_by_fabrics(nodes)
        nodes = self.filter_by_fabric_classes(nodes)
        nodes = self.filter_by_cpu_count(nodes)
        nodes = self.filter_by_mem(nodes)
        nodes = self.filter_by_pod_or_pod_type(nodes)
        nodes = self.filter_by_devices(nodes)
        return nodes.distinct()

    def filter_by_interfaces(self, filtered_nodes):
        compatible_interfaces = {}
        interfaces_label_map = self.cleaned_data.get(
            self.get_field_name("interfaces")
        )
        if interfaces_label_map is not None:
            result = nodes_by_interface(interfaces_label_map)
            if result.node_ids is not None:
                filtered_nodes = filtered_nodes.filter(id__in=result.node_ids)
                compatible_interfaces = result.label_map
        return compatible_interfaces, filtered_nodes

    def filter_by_storage(self, filtered_nodes):
        compatible_nodes = {}  # Maps node/storage to named storage constraints
        storage = self.cleaned_data.get(self.get_field_name("storage"))
        if storage:
            compatible_nodes = nodes_by_storage(storage)
            node_ids = list(compatible_nodes)
            if node_ids is not None:
                filtered_nodes = filtered_nodes.filter(id__in=node_ids)
        return compatible_nodes, filtered_nodes

    def filter_by_fabric_classes(self, filtered_nodes):
        fabric_classes = self.cleaned_data.get(
            self.get_field_name("fabric_classes")
        )
        if fabric_classes is not None and len(fabric_classes) > 0:
            filtered_nodes = filtered_nodes.filter(
                current_config__interface__vlan__fabric__class_type__in=fabric_classes
            )
        not_fabric_classes = self.cleaned_data.get(
            self.get_field_name("not_fabric_classes")
        )
        if not_fabric_classes is not None and len(not_fabric_classes) > 0:
            filtered_nodes = filtered_nodes.exclude(
                current_config__interface__vlan__fabric__class_type__in=not_fabric_classes
            )
        return filtered_nodes

    def filter_by_fabrics(self, filtered_nodes):
        fabrics = self.cleaned_data.get(self.get_field_name("fabrics"))
        if fabrics is not None and len(fabrics) > 0:
            # XXX mpontillo 2015-10-30 need to also handle fabrics whose name
            # is null (fabric-<id>).
            filtered_nodes = filtered_nodes.filter(
                current_config__interface__vlan__fabric__name__in=fabrics
            )
        not_fabrics = self.cleaned_data.get(self.get_field_name("not_fabrics"))
        if not_fabrics is not None and len(not_fabrics) > 0:
            # XXX mpontillo 2015-10-30 need to also handle fabrics whose name
            # is null (fabric-<id>).
            filtered_nodes = filtered_nodes.exclude(
                current_config__interface__vlan__fabric__name__in=not_fabrics
            )
        return filtered_nodes

    def filter_by_vlans(self, filtered_nodes):
        vlans = self.cleaned_data.get(self.get_field_name("vlans"))
        if vlans is not None and len(vlans) > 0:
            for vlan in set(vlans):
                filtered_nodes = filtered_nodes.filter(
                    current_config__interface__vlan=vlan
                )
        not_vlans = self.cleaned_data.get(self.get_field_name("not_vlans"))
        if not_vlans is not None and len(not_vlans) > 0:
            for not_vlan in set(not_vlans):
                filtered_nodes = filtered_nodes.exclude(
                    current_config__interface__vlan=not_vlan
                )
        return filtered_nodes

    def filter_by_subnets(self, filtered_nodes):
        subnets = self.cleaned_data.get(self.get_field_name("subnets"))
        if subnets is not None and len(subnets) > 0:
            for subnet in set(subnets):
                filtered_nodes = filtered_nodes.filter(
                    current_config__interface__ip_addresses__subnet=subnet
                )
        not_subnets = self.cleaned_data.get(self.get_field_name("not_subnets"))
        if not_subnets is not None and len(not_subnets) > 0:
            for not_subnet in set(not_subnets):
                filtered_nodes = filtered_nodes.exclude(
                    current_config__interface__ip_addresses__subnet=not_subnet
                )
        return filtered_nodes

    def filter_by_link_speed(self, filtered_nodes):
        link_speed = self.cleaned_data.get(self.get_field_name("link_speed"))
        if link_speed:
            filtered_nodes = filtered_nodes.filter(
                current_config__interface__link_speed__gte=link_speed
            )
        return filtered_nodes

    def filter_by_zone(self, filtered_nodes):
        zone = self.cleaned_data.get(self.get_field_name("zone"))
        if zone:
            zone_obj = Zone.objects.get(name=zone)
            filtered_nodes = filtered_nodes.filter(zone=zone_obj)
        not_in_zone = self.cleaned_data.get(self.get_field_name("not_in_zone"))
        if not_in_zone:
            not_in_zones = Zone.objects.filter(name__in=not_in_zone)
            filtered_nodes = filtered_nodes.exclude(zone__in=not_in_zones)
        return filtered_nodes

    def filter_by_pool(self, filtered_nodes):
        pool_name = self.cleaned_data.get(self.get_field_name("pool"))
        if pool_name:
            pool = ResourcePool.objects.get(name=pool_name)
            filtered_nodes = filtered_nodes.filter(pool=pool)
        not_in_pool = self.cleaned_data.get(self.get_field_name("not_in_pool"))
        if not_in_pool:
            pools_to_exclude = ResourcePool.objects.filter(
                name__in=not_in_pool
            )
            filtered_nodes = filtered_nodes.exclude(pool__in=pools_to_exclude)
        return filtered_nodes

    def filter_by_tags(self, filtered_nodes):
        tags = self.cleaned_data.get(self.get_field_name("tags"))
        if tags:
            for tag in tags:
                filtered_nodes = filtered_nodes.filter(tags__name=tag)
        not_tags = self.cleaned_data.get(self.get_field_name("not_tags"))
        if len(not_tags) > 0:
            for not_tag in not_tags:
                filtered_nodes = filtered_nodes.exclude(tags__name=not_tag)
        return filtered_nodes

    def filter_by_mem(self, filtered_nodes):
        mem = self.cleaned_data.get(self.get_field_name("mem"))
        if mem:
            filtered_nodes = filtered_nodes.filter(memory__gte=mem)
        return filtered_nodes

    def filter_by_cpu_count(self, filtered_nodes):
        cpu_count = self.cleaned_data.get(self.get_field_name("cpu_count"))
        if cpu_count:
            filtered_nodes = filtered_nodes.filter(cpu_count__gte=cpu_count)
        return filtered_nodes

    def filter_by_arch(self, filtered_nodes):
        arch = self.cleaned_data.get(self.get_field_name("arch"))
        if arch:
            filtered_nodes = filtered_nodes.filter(architecture__in=arch)
        return filtered_nodes

    def filter_by_system_id(self, filtered_nodes):
        # Filter by system_id.
        system_id = self.cleaned_data.get(self.get_field_name("system_id"))
        if system_id:
            filtered_nodes = filtered_nodes.filter(system_id=system_id)
        return filtered_nodes

    def filter_by_pod_or_pod_type(self, filtered_nodes):
        # Filter by pod, pod type, not_pod or not_pod_type.
        # We are filtering for all of these to keep the query count down.
        pod = self.cleaned_data.get(self.get_field_name("pod"))
        not_pod = self.cleaned_data.get(self.get_field_name("not_pod"))
        pod_type = self.cleaned_data.get(self.get_field_name("pod_type"))
        not_pod_type = self.cleaned_data.get(
            self.get_field_name("not_pod_type")
        )
        if pod or pod_type or not_pod or not_pod_type:
            pods = Pod.objects.all()
            if pod:
                pods = pods.filter(name=pod)
            if not pod:
                pods = pods.exclude(name=not_pod)
            if pod_type:
                pods = pods.filter(power_type=pod_type)
            if not_pod_type:
                pods = pods.exclude(power_type=not_pod_type)
            filtered_nodes = filtered_nodes.filter(
                bmc_id__in=pods.values_list("id", flat=True)
            )
        return filtered_nodes.distinct()

    def filter_by_devices(self, filtered_nodes):
        devices = self.cleaned_data.get(self.get_field_name("devices"))
        if devices:
            filters = {}
            for f in devices.split(","):
                key, value = f.split("=", 1)
                filters[f"current_config__nodedevice__{key}__iexact"] = value
            filtered_nodes = filtered_nodes.filter(**filters)
        return filtered_nodes


class AcquireNodeForm(FilterNodeForm):
    """A form handling the constraints used to acquire a node."""

    name = forms.CharField(
        label="The hostname of the desired node", required=False
    )

    system_id = forms.CharField(
        label="The system_id of the desired node", required=False
    )

    def _apply_filters(self, nodes):
        nodes = super()._apply_filters(nodes)
        nodes = self.filter_by_hostname(nodes)
        nodes = self.filter_by_system_id(nodes)
        return nodes

    def filter_by_hostname(self, filtered_nodes):
        # Filter by hostname.
        hostname = self.cleaned_data.get(self.get_field_name("name"))
        if hostname:
            # If the given hostname has a domain part, try matching
            # against the nodes' FQDN.
            if "." in hostname:
                host, domain = hostname.split(".", 1)
                hostname_clause = Q(hostname=host)
                domain_clause = Q(domain__name=domain)
                clause = hostname_clause & domain_clause
            else:
                clause = Q(hostname=hostname)
            filtered_nodes = filtered_nodes.filter(clause)
        return filtered_nodes

    def filter_nodes(self, nodes):
        result = super().filter_nodes(nodes)
        filtered_nodes, compatible_nodes, compatible_interfaces = result
        filtered_nodes = self.reorder_nodes_by_cost(filtered_nodes)
        return filtered_nodes, compatible_nodes, compatible_interfaces

    def reorder_nodes_by_cost(self, filtered_nodes):
        # This uses a very simple procedure to compute a machine's
        # cost. This procedure is loosely based on how ec2 computes
        # the costs of machines. This is here to give a hint to let
        # the call to acquire() decide which machine to return based
        # on the machine's cost when multiple machines match the
        # constraints.
        filtered_nodes = filtered_nodes.extra(
            select={"cost": "cpu_count + memory / 1024."}
        )
        return filtered_nodes.order_by("cost")


class ReadNodesForm(FilterNodeForm):

    id = UnconstrainedMultipleChoiceField(
        label="System IDs to filter on", required=False
    )

    hostname = UnconstrainedMultipleChoiceField(
        label="Hostnames to filter on", required=False
    )

    mac_address = ValidatorMultipleChoiceField(
        validator=mac_validator,
        label="MAC addresses to filter on",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: invalid MAC address format"
        },
    )

    domain = UnconstrainedMultipleChoiceField(
        label="Domain names to filter on", required=False
    )

    agent_name = forms.CharField(
        label="Only include nodes with events matching the agent name",
        required=False,
    )

    status = forms.ChoiceField(
        label="Only includes nodes with the specified status",
        choices=NODE_STATUS_SHORT_LABEL_CHOICES,
        required=False,
    )

    def _apply_filters(self, nodes):
        nodes = super()._apply_filters(nodes)
        nodes = self.filter_by_ids(nodes)
        nodes = self.filter_by_hostnames(nodes)
        nodes = self.filter_by_mac_addresses(nodes)
        nodes = self.filter_by_domain(nodes)
        nodes = self.filter_by_agent_name(nodes)
        nodes = self.filter_by_status(nodes)
        return nodes

    def filter_by_ids(self, filtered_nodes):
        ids = self.cleaned_data.get(self.get_field_name("id"))
        if ids:
            filtered_nodes = filtered_nodes.filter(system_id__in=ids)
        return filtered_nodes

    def filter_by_hostnames(self, filtered_nodes):
        hostnames = self.cleaned_data.get(self.get_field_name("hostname"))
        if hostnames:
            filtered_nodes = filtered_nodes.filter(hostname__in=hostnames)
        return filtered_nodes

    def filter_by_mac_addresses(self, filtered_nodes):
        mac_addresses = self.cleaned_data.get(
            self.get_field_name("mac_address")
        )
        if mac_addresses:
            filtered_nodes = filtered_nodes.filter(
                current_config__interface__mac_address__in=mac_addresses
            )
        return filtered_nodes

    def filter_by_domain(self, filtered_nodes):
        domains = self.cleaned_data.get(self.get_field_name("domain"))
        if domains:
            filtered_nodes = filtered_nodes.filter(domain__name__in=domains)
        return filtered_nodes

    def filter_by_agent_name(self, filtered_nodes):
        field_name = self.get_field_name("agent_name")
        if field_name in self.data:
            agent_name = self.cleaned_data.get(field_name)
            filtered_nodes = filtered_nodes.filter(agent_name=agent_name)
        return filtered_nodes

    def filter_by_status(self, filtered_nodes):
        status = self.cleaned_data.get(self.get_field_name("status"))
        if status:
            status_id = getattr(NODE_STATUS, status.upper())
            filtered_nodes = filtered_nodes.filter(status=status_id)
        return filtered_nodes
