# Copyright 2013-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import defaultdict
from copy import deepcopy
from functools import reduce
import itertools
from itertools import chain
import re

import attr
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Model, Q
from django.forms.fields import Field
from netaddr import IPAddress

from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_SHORT_LABEL_CHOICES,
    POWER_STATE,
    POWER_STATE_CHOICES,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUS_LABEL_CHOICES,
)
from maasserver.fields import MAC_VALIDATOR, MODEL_NAME_VALIDATOR
import maasserver.forms as maasserver_forms
from maasserver.forms import (
    ConstrainedMultipleChoiceField,
    MultipleChoiceField,
    TypedMultipleChoiceField,
    UnconstrainedMultipleChoiceField,
    UnconstrainedTypedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
from maasserver.models import (
    BlockDevice,
    Filesystem,
    Interface,
    Node,
    Partition,
    ResourcePool,
    Subnet,
    Tag,
    User,
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
    return groups


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


def detect_nonexistent_names(model_class, names, name_field="name"):
    """Check for, and return, names of nonexistent objects.

    Used for checking object names as passed to the `FilterNodeForm`.

    :param model_class: A model class that has a name attribute.
    :param names: List, tuple, or set of purpoprted zone names.
    :return: A sorted list of those names that did not name existing zones.
    """
    names = names or []
    assert isinstance(names, (list, tuple, set))
    if len(names) == 0:
        return []
    existing_names = set(
        model_class.objects.all().values_list(name_field, flat=True)
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


STATIC_FILTER_FIELDS = (
    "arch",
    "power_state",
    "simple_status",
    "status",
)


GROUPABLE_FIELDS = (
    "arch",
    "domain",
    "owner",
    "pod_type",
    "pod",
    "pool",
    "power_state",
    "status",
    "zone",
    "parent",
)


def str_or_none(x):
    return str(x) if x is not None else x


def get_field_argument_type(field):
    if isinstance(field, (forms.FloatField,)):
        return "float"
    elif isinstance(field, (forms.IntegerField,)):
        return "int"
    elif isinstance(field, (forms.CharField,)):
        return "str"
    elif isinstance(field, (forms.BooleanField, forms.NullBooleanField)):
        return "bool"
    elif isinstance(field, (TypedMultipleChoiceField)):
        ftype = "str" if field.coerce is str_or_none else field.coerce.__name__
        return f"list[{ftype}]"
    elif isinstance(field, (MultipleChoiceField)):
        return "list[str]"
    elif isinstance(field, (LabeledConstraintMapField)):
        return "str"
    elif isinstance(field, (forms.ChoiceField,)):
        return "str"
    else:
        return "str"


def _match_gte(field, values):
    return [Q(**{f"{field}__gte": min(values)})]


def _match_any(field, values):
    return [Q(**{f"{field}__in": set(values)})]


def _match_all(field, values):
    return [Q(**{f"{field}": v}) for v in set(values)]


def _match_compose_value(field, values):
    subfields = field.split(".", 1)
    return [
        reduce(
            lambda x, y: x.__and__(Q(**{f"{y[0]}": y[1]})),
            zip(subfields, v.split(".", 1)),
            Q(),
        )
        for v in values
    ]


def _match_substring(field, values):
    query = Q()
    for substr in values:
        if substr is None:
            query |= Q(**{f"{field}__isnull": True})
        elif substr.startswith("="):
            query |= Q(**{f"{field}__exact": substr[1:]})
        else:
            query |= Q(**{f"{field}__icontains": substr})
    return [query]


def _match_substring_kv(field, values):
    query = Q()
    for kv in values:
        (key, val) = kv if isinstance(kv, tuple) else ("", kv)
        qkey = Q(**{f"{field}__key": key}) if key else Q()
        if val.startswith("="):
            query |= qkey & Q(**{f"{field}__value__exact": val[1:]})
        else:
            query |= qkey & Q(**{f"{field}__value__icontains": val})
    return [query]


class FilterNodeForm(forms.Form):
    """A form for filtering nodes."""

    # This becomes a multiple-choice field during cleaning, to accommodate
    # architecture wildcards.
    arch = UnconstrainedMultipleChoiceField(
        label="Architecture", required=False
    )

    not_arch = UnconstrainedMultipleChoiceField(
        label="Architecture", required=False
    )

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

    link_speed = UnconstrainedTypedMultipleChoiceField(
        label="Link speed",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid link speed: number required."
        },
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

    zone = UnconstrainedMultipleChoiceField(
        label="Physical zone", required=False, coerce=str_or_none
    )

    not_in_zone = ValidatorMultipleChoiceField(
        validator=MODEL_NAME_VALIDATOR,
        label="Not in zone",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: must list physical zones."
        },
    )

    pool = UnconstrainedMultipleChoiceField(
        label="Resource pool", required=False, coerce=str_or_none
    )

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

    cpu_count = UnconstrainedTypedMultipleChoiceField(
        label="CPU count",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid CPU count: number required."
        },
    )

    cpu_speed = UnconstrainedTypedMultipleChoiceField(
        label="CPU speed",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid CPU speed: number required."
        },
    )

    mem = UnconstrainedTypedMultipleChoiceField(
        label="Memory",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of MiB required."
        },
    )

    pod = UnconstrainedMultipleChoiceField(
        label="The name of the desired pod", required=False, coerce=str_or_none
    )

    not_pod = UnconstrainedMultipleChoiceField(
        label="The name of the undesired pod",
        required=False,
        coerce=str_or_none,
    )

    pod_type = UnconstrainedMultipleChoiceField(
        label="The power_type of the desired pod",
        required=False,
        coerce=str_or_none,
    )

    not_pod_type = UnconstrainedMultipleChoiceField(
        label="The power_type of the undesired pod",
        required=False,
        coerce=str_or_none,
    )

    owner = UnconstrainedMultipleChoiceField(
        label="Owner", required=False, coerce=str_or_none
    )

    not_owner = UnconstrainedMultipleChoiceField(
        label="Owner", required=False, coerce=str_or_none
    )

    power_state = ConstrainedMultipleChoiceField(
        label="Power State",
        choices=POWER_STATE_CHOICES,
        required=False,
        clean_prefix="=",
    )

    not_power_state = ConstrainedMultipleChoiceField(
        label="Power State",
        choices=POWER_STATE_CHOICES,
        required=False,
        clean_prefix="=",
    )

    ignore_unknown_constraints = False

    NODE_FILTERS = {
        "fabric_classes": (
            "current_config__interface__vlan__fabric__class_type",
            _match_any,
        ),
        "fabrics": (
            "current_config__interface__vlan__fabric__name",
            _match_any,
        ),
        "vlans": ("current_config__interface__vlan", _match_any),
        "zone": ("zone__name", _match_any),
        "pool": ("pool__name", _match_any),
        "mem": ("memory", _match_gte),
        "cpu_count": ("cpu_count", _match_gte),
        "cpu_speed": ("cpu_speed", _match_gte),
        "arch": ("architecture", _match_any),
        "link_speed": ("current_config__interface__link_speed", _match_gte),
        "tags": ("tags__name", _match_all),
        "subnets": (
            "current_config__interface__ip_addresses__subnet",
            _match_all,
        ),
        "pod": ("bmc__name", _match_any),
        "pod_type": ("bmc__power_type", _match_any),
        "owner": ("owner__username", _match_any),
        "power_state": ("power_state", _match_any),
    }

    NODE_EXCLUDES = {
        "not_fabric_classes": (
            "current_config__interface__vlan__fabric__class_type",
            _match_any,
        ),
        "not_fabrics": (
            "current_config__interface__vlan__fabric__name",
            _match_any,
        ),
        "not_vlans": ("current_config__interface__vlan", _match_any),
        "not_in_zone": ("zone__name", _match_any),
        "not_in_pool": ("pool__name", _match_any),
        "not_arch": ("architecture", _match_any),
        "not_tags": ("tags__name", _match_any),
        "not_subnets": (
            "current_config__interface__ip_addresses__subnet",
            _match_any,
        ),
        "not_system_id": ("system_id", _match_any),
        "not_pod": ("bmc__name", _match_any),
        "not_pod_type": ("bmc__power_type", _match_any),
        "not_owner": ("owner__username", _match_any),
        "not_power_state": ("power_state", _match_any),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_filters = deepcopy(self.NODE_FILTERS)
        self.node_excludes = deepcopy(self.NODE_EXCLUDES)

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
        values = self.cleaned_data["arch"]
        arches = []
        for value in values:
            if value in usable_architectures:
                # Full 'arch/subarch' specified directly.
                arches.append(value)
            elif value in architecture_wildcards:
                # Try to expand 'arch' to all available 'arch/subarch'
                # matches.
                arches.extend(architecture_wildcards[value])
            else:
                set_form_error(
                    self,
                    "arch",
                    "Architecture not recognised.",
                )
                return None
        return arches

    def _set_clean_tags_error(self, tag_names, db_tag_names):
        unknown_tags = tag_names.difference(db_tag_names)
        error_msg = "No such tag(s): %s." % ", ".join(
            "'%s'" % tag for tag in unknown_tags
        )
        set_form_error(self, "tags", error_msg)

    def clean_tags(self):
        value = self.cleaned_data["tags"]
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
                self._set_clean_tags_error(tag_names, db_tag_names)
                return None
            return tag_names
        return None

    def _set_zone_error(self, value, field):
        if type(value) == list:
            error_msg = "No such zone(s): %s." % ", ".join(value)
        else:
            error_msg = "No such zone: '%s'." % value
        set_form_error(self, field, error_msg)

    def clean_zone(self):
        values = self.cleaned_data["zone"]
        nonexistent_names = detect_nonexistent_names(Zone, values)
        if nonexistent_names:
            self._set_zone_error(nonexistent_names, "zone")
            return None
        return values

    def clean_not_in_zone(self):
        values = self.cleaned_data["not_in_zone"]
        nonexistent_names = detect_nonexistent_names(Zone, values)
        if nonexistent_names:
            self._set_zone_error(nonexistent_names, "not_in_zone")
            return None
        return values

    def _set_pool_error(self, value, field):
        if type(value) == list:
            error_msg = "No such pool(s): %s." % ", ".join(value)
        else:
            error_msg = "No such pool: '%s'." % value
        set_form_error(self, field, error_msg)

    def clean_pool(self):
        values = self.cleaned_data["pool"]
        nonexistent_names = detect_nonexistent_names(ResourcePool, values)
        if nonexistent_names:
            self._set_pool_error(nonexistent_names, "pool")
            return None
        return values

    def clean_not_in_pool(self):
        values = self.cleaned_data["not_in_pool"]
        nonexistent_names = detect_nonexistent_names(ResourcePool, values)
        if nonexistent_names:
            self._set_pool_error(nonexistent_names, "not_in_pool")
            return None
        return values

    def _clean_specifiers(self, model, specifiers):
        if not specifiers:
            return []
        objects = set(model.objects.filter_by_specifiers(specifiers))
        if len(objects) == 0:
            raise ValidationError(
                "No matching %s found." % model._meta.verbose_name_plural
            )
        return objects

    def clean_subnets(self):
        value = self.cleaned_data["subnets"]
        return self._clean_specifiers(Subnet, value)

    def clean_not_subnets(self):
        value = self.cleaned_data["not_subnets"]
        return self._clean_specifiers(Subnet, value)

    def clean_vlans(self):
        value = self.cleaned_data["vlans"]
        return self._clean_specifiers(VLAN, value)

    def clean_not_vlans(self):
        value = self.cleaned_data["not_vlans"]
        return self._clean_specifiers(VLAN, value)

    def clean_owner(self):
        values = self.cleaned_data["owner"]
        nonexistent_names = detect_nonexistent_names(User, values, "username")
        if nonexistent_names:
            set_form_error(
                self, "owner", "No such owner: '%s'." % nonexistent_names[0]
            )
            return None
        return values

    def clean_power_state(self):
        values = self.cleaned_data["power_state"]
        return [getattr(POWER_STATE, a.upper()) for a in values]

    def clean_not_power_state(self):
        values = self.cleaned_data["not_power_state"]
        return [getattr(POWER_STATE, a.upper()) for a in values]

    def clean(self):
        if not self.ignore_unknown_constraints:
            unknown_constraints = set(self.data).difference(set(self.fields))
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
        nodes = self._apply_conditions(nodes, self.node_filters)
        nodes = self._apply_exclusions(nodes, self.node_excludes)
        nodes = self.filter_by_devices(nodes)
        return nodes.distinct()

    def _apply_conditions(self, qs, filters):
        for form_field, (db_field, cond) in filters.items():
            values = self.cleaned_data.get(form_field, None)
            if values:
                qs = reduce(
                    lambda q, c: q.filter(c),
                    cond(db_field, values),
                    qs,
                )
        return qs

    def _apply_exclusions(self, qs, filters):
        for not_form_field, (db_field, cond) in filters.items():
            values = self.cleaned_data.get(not_form_field, None)
            if values:
                qs = reduce(
                    lambda q, c: q.exclude(c),
                    cond(db_field, values),
                    qs,
                )
        return qs

    def filter_by_interfaces(self, filtered_nodes):
        compatible_interfaces = {}
        interfaces_label_map = self.cleaned_data.get("interfaces")
        if interfaces_label_map is not None:
            result = nodes_by_interface(interfaces_label_map)
            if result.node_ids is not None:
                filtered_nodes = filtered_nodes.filter(id__in=result.node_ids)
                compatible_interfaces = result.label_map
        return compatible_interfaces, filtered_nodes

    def filter_by_storage(self, filtered_nodes):
        compatible_nodes = {}  # Maps node/storage to named storage constraints
        storage = self.cleaned_data.get("storage")
        if storage:
            compatible_nodes = nodes_by_storage(storage)
            node_ids = list(compatible_nodes)
            if node_ids is not None:
                filtered_nodes = filtered_nodes.filter(id__in=node_ids)
        return compatible_nodes, filtered_nodes

    def filter_by_devices(self, filtered_nodes):
        devices = self.cleaned_data.get("devices")
        if devices:
            filters = {}
            for f in devices.split(","):
                key, value = f.split("=", 1)
                filters[f"current_config__nodedevice__{key}__iexact"] = value
            filtered_nodes = filtered_nodes.filter(**filters)
        return filtered_nodes


class AcquireNodeForm(FilterNodeForm):
    """A form handling the constraints used to acquire a node."""

    name = UnconstrainedMultipleChoiceField(
        label="The hostname of the desired node", required=False
    )

    system_id = UnconstrainedMultipleChoiceField(
        label="The system_id of the desired node", required=False
    )

    ACQUIRE_CONDs = {
        "system_id": ("system_id", _match_any),
        "name": ("hostname.domain__name", _match_compose_value),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_filters.update(self.ACQUIRE_CONDs)

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
            select={
                "cost": "maasserver_node.cpu_count + maasserver_node.memory / 1024."
            }
        )
        return filtered_nodes.order_by("cost")


class ReadNodesForm(FilterNodeForm):
    id = UnconstrainedMultipleChoiceField(
        label="System IDs to filter on", required=False
    )

    not_id = UnconstrainedMultipleChoiceField(
        label="System IDs to ignore", required=False
    )

    hostname = UnconstrainedMultipleChoiceField(
        label="Hostnames to filter on", required=False
    )

    not_hostname = UnconstrainedMultipleChoiceField(
        label="Hostnames to ignore", required=False
    )

    mac_address = ValidatorMultipleChoiceField(
        validator=MAC_VALIDATOR,
        label="MAC addresses to filter on",
        required=False,
        error_messages={
            "invalid_list": "Invalid parameter: invalid MAC address format"
        },
    )

    domain = UnconstrainedMultipleChoiceField(
        label="Domain names to filter on", required=False, coerce=str_or_none
    )

    not_domain = UnconstrainedMultipleChoiceField(
        label="Domain names to ignore", required=False, coerce=str_or_none
    )

    agent_name = UnconstrainedMultipleChoiceField(
        label="Only include nodes with events matching the agent name",
        required=False,
        coerce=str_or_none,
    )

    not_agent_name = UnconstrainedMultipleChoiceField(
        label="Excludes nodes with events matching the agent name",
        required=False,
        coerce=str_or_none,
    )

    status = ConstrainedMultipleChoiceField(
        label="Only includes nodes with the specified status",
        choices=NODE_STATUS_SHORT_LABEL_CHOICES,
        required=False,
        clean_prefix="=",
    )

    not_status = ConstrainedMultipleChoiceField(
        label="Exclude nodes with the specified status",
        choices=NODE_STATUS_SHORT_LABEL_CHOICES,
        required=False,
        clean_prefix="=",
    )

    simple_status = ConstrainedMultipleChoiceField(
        label="Only includes nodes with the specified simplified status",
        choices=SIMPLIFIED_NODE_STATUS_LABEL_CHOICES,
        required=False,
        clean_prefix="=",
    )

    not_simple_status = ConstrainedMultipleChoiceField(
        label="Exclude nodes with the specified simplified status",
        choices=SIMPLIFIED_NODE_STATUS_LABEL_CHOICES,
        required=False,
        clean_prefix="=",
    )

    READ_CONDs = {
        "id": ("system_id", _match_any),
        "hostname": ("hostname", _match_any),
        "mac_address": ("current_config__interface__mac_address", _match_any),
        "domain": ("domain__name", _match_any),
        "agent_name": ("agent_name", _match_any),
        "status": ("status", _match_any),
        "simple_status": ("simple_status", _match_any),
    }

    READ_NOT_CONDs = {
        "not_id": ("system_id", _match_any),
        "not_hostname": ("hostname", _match_any),
        "not_domain": ("domain__name", _match_any),
        "not_agent_name": ("agent_name", _match_any),
        "not_status": ("status", _match_any),
        "not_simple_status": ("simple_status", _match_any),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_filters.update(self.READ_CONDs)
        self.node_excludes.update(self.READ_NOT_CONDs)

    def clean_status(self):
        values = self.cleaned_data["status"]
        return [getattr(NODE_STATUS, a.upper()) for a in values]

    def clean_not_status(self):
        values = self.cleaned_data["not_status"]
        return [getattr(NODE_STATUS, a.upper()) for a in values]

    def clean_simple_status(self):
        values = self.cleaned_data["simple_status"]
        return [getattr(SIMPLIFIED_NODE_STATUS, a.upper()) for a in values]

    def clean_not_simple_status(self):
        values = self.cleaned_data["not_simple_status"]
        return [getattr(SIMPLIFIED_NODE_STATUS, a.upper()) for a in values]


class FreeTextFilterNodeForm(ReadNodesForm):
    free_text = UnconstrainedMultipleChoiceField(
        label="Free-text search on all string fields",
        required=False,
    )

    mac_address = UnconstrainedMultipleChoiceField(
        label="MAC addresses to filter on",
        required=False,
    )

    not_mac_address = UnconstrainedMultipleChoiceField(
        label="MAC addresses to filter on",
        required=False,
    )

    description = UnconstrainedMultipleChoiceField(
        label="The description of the desired node",
        required=False,
        coerce=str_or_none,
    )

    osystem = UnconstrainedMultipleChoiceField(
        label="The OS of the desired node", required=False, coerce=str_or_none
    )

    not_osystem = UnconstrainedMultipleChoiceField(
        label="OS to ignore", required=False, coerce=str_or_none
    )

    distro_series = UnconstrainedMultipleChoiceField(
        label="The OS distribution of the desired node",
        required=False,
        coerce=str_or_none,
    )

    not_distro_series = UnconstrainedMultipleChoiceField(
        label="OS distribution to ignore", required=False, coerce=str_or_none
    )

    error_description = UnconstrainedMultipleChoiceField(
        label="node error description", required=False, coerce=str_or_none
    )

    ip_addresses = UnconstrainedMultipleChoiceField(
        label="Node's IP address", required=False, coerce=str_or_none
    )

    not_ip_addresses = UnconstrainedMultipleChoiceField(
        label="IP address to ignore", required=False, coerce=str_or_none
    )

    spaces = UnconstrainedMultipleChoiceField(
        label="Node's spaces", required=False, coerce=str_or_none
    )

    not_spaces = UnconstrainedMultipleChoiceField(
        label="Node's spaces", required=False, coerce=str_or_none
    )

    workloads = UnconstrainedMultipleChoiceField(
        label="Node's workload annotations", required=False, coerce=str_or_none
    )

    not_workloads = UnconstrainedMultipleChoiceField(
        label="Node's workload annotations", required=False, coerce=str_or_none
    )

    not_link_speed = UnconstrainedTypedMultipleChoiceField(
        label="Link speed",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid link speed: number required."
        },
    )

    not_cpu_count = UnconstrainedTypedMultipleChoiceField(
        label="CPU count",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid CPU count: number required."
        },
    )

    not_cpu_speed = UnconstrainedTypedMultipleChoiceField(
        label="CPU speed",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid CPU speed: number required."
        },
    )

    not_mem = UnconstrainedTypedMultipleChoiceField(
        label="Memory",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of MiB required."
        },
    )

    physical_disk_count = UnconstrainedTypedMultipleChoiceField(
        label="Physical disk Count",
        coerce=int,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of disks required."
        },
    )

    not_physical_disk_count = UnconstrainedTypedMultipleChoiceField(
        label="Physical disk Count",
        coerce=int,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of disks required."
        },
    )

    total_storage = UnconstrainedTypedMultipleChoiceField(
        label="Total storage",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of MiB required."
        },
    )

    not_total_storage = UnconstrainedTypedMultipleChoiceField(
        label="Total storage",
        coerce=float,
        required=False,
        error_messages={
            "invalid_choice": "Invalid memory: number of MiB required."
        },
    )

    pxe_mac = UnconstrainedMultipleChoiceField(
        label="Boot interface MAC address", required=False
    )

    not_pxe_mac = UnconstrainedMultipleChoiceField(
        label="Boot interface MAC address", required=False
    )

    fabric_name = UnconstrainedMultipleChoiceField(
        label="Boot interface Fabric", required=False
    )

    not_fabric_name = UnconstrainedMultipleChoiceField(
        label="Boot interface Fabric", required=False
    )

    fqdn = UnconstrainedMultipleChoiceField(label="Node FQDN", required=False)

    not_fqdn = UnconstrainedMultipleChoiceField(
        label="Node FQDN", required=False
    )

    interfaces = UnconstrainedMultipleChoiceField(
        label="Interfaces", required=False
    )

    devices = UnconstrainedMultipleChoiceField(label="Devices", required=False)

    storage = UnconstrainedMultipleChoiceField(label="Storage", required=False)

    parent = UnconstrainedMultipleChoiceField(
        label="Parent node", required=False, coerce=str_or_none
    )

    FREETEXT_FILTERS = {
        "hostname": ("hostname", _match_substring),
        "description": ("description", _match_substring),
        "distro_series": ("distro_series", _match_substring),
        "osystem": ("osystem", _match_substring),
        "error_description": ("error_description", _match_substring),
        "mac_address": (
            "current_config__interface__mac_address",
            _match_substring,
        ),
        "domain": ("domain__name", _match_substring),
        "agent_name": ("agent_name", _match_substring),
        "fabric_classes": (
            "current_config__interface__vlan__fabric__class_type",
            _match_substring,
        ),
        "fabrics": (
            "current_config__interface__vlan__fabric__name",
            _match_substring,
        ),
        "zone": ("zone__name", _match_substring),
        "pool": ("pool__name", _match_substring),
        "arch": ("architecture", _match_substring),
        "tags": ("tags__name", _match_substring),
        "vlans": ("current_config__interface__vlan__name", _match_substring),
        "pod": ("bmc__name", _match_substring),
        "pod_type": ("bmc__power_type", _match_substring),
        "owner": ("owner__username", _match_substring),
        "subnets": (
            "current_config__interface__ip_addresses__subnet__cidr",
            _match_substring,
        ),
        "ip_addresses": (
            "current_config__interface__ip_addresses__ip",
            _match_substring,
        ),
        "spaces": (
            "current_config__interface__vlan__space__name",
            _match_substring,
        ),
        "workloads": (
            "ownerdata",
            _match_substring_kv,
        ),
        "pxe_mac": ("pxe_mac", _match_substring),
        "fabric_name": ("fabric_name", _match_substring),
        "fqdn": ("node_fqdn", _match_substring),
        "parent": ("parent__system_id", _match_substring),
    }

    UPDATE_FILTERS = {
        "link_speed": ("current_config__interface__link_speed", _match_any),
        "cpu_count": ("cpu_count", _match_any),
        "cpu_speed": ("cpu_speed", _match_any),
        "mem": ("memory", _match_any),
        "physical_disk_count": ("physical_disk_count", _match_any),
        "total_storage": ("total_storage", _match_any),
        "numa_nodes_count": ("numa_nodes_count", _match_any),
    }

    FREETEXT_EXCLUDES = {
        "not_fabric_classes": (
            "current_config__interface__vlan__fabric__class_type",
            _match_substring,
        ),
        "not_fabrics": (
            "current_config__interface__vlan__fabric__name",
            _match_substring,
        ),
        "not_in_zone": ("zone__name", _match_substring),
        "not_in_pool": ("pool__name", _match_substring),
        "not_arch": ("architecture", _match_substring),
        "not_tags": ("tags__name", _match_substring),
        "not_system_id": ("system_id", _match_substring),
        "not_pod": ("bmc__name", _match_substring),
        "not_pod_type": ("bmc__power_type", _match_substring),
        "not_owner": ("owner__username", _match_substring),
        "not_subnets": (
            "current_config__interface__ip_addresses__subnet__cidr",
            _match_substring,
        ),
        "not_vlans": (
            "current_config__interface__vlan__name",
            _match_substring,
        ),
        "not_ip_addresses": (
            "current_config__interface__ip_addresses__ip",
            _match_substring,
        ),
        "not_distro_series": ("distro_series", _match_substring),
        "not_osystem": ("osystem", _match_substring),
        "not_mac_address": (
            "current_config__interface__mac_address",
            _match_substring,
        ),
        "not_spaces": (
            "current_config__interface__vlan__space__name",
            _match_substring,
        ),
        "not_workloads": (
            "ownerdata",
            _match_substring_kv,
        ),
        "not_pxe_mac": ("pxe_mac", _match_substring),
        "not_fabric_name": ("fabric_name", _match_substring),
        "not_fqdn": ("node_fqdn", _match_substring),
    }

    UPDATE_EXCLUDES = {
        "not_link_speed": (
            "current_config__interface__link_speed",
            _match_any,
        ),
        "not_cpu_count": ("cpu_count", _match_any),
        "not_cpu_speed": ("cpu_speed", _match_any),
        "not_mem": ("memory", _match_any),
        "not_physical_disk_count": ("physical_disk_count", _match_any),
        "not_total_storage": ("total_storage", _match_any),
        "not_numa_nodes_count": ("numa_nodes_count", _match_any),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.node_filters.update(self.FREETEXT_FILTERS)
        self.node_filters.update(self.UPDATE_FILTERS)
        self.node_excludes.update(self.FREETEXT_EXCLUDES)
        self.node_excludes.update(self.UPDATE_EXCLUDES)

    def clean_workloads(self):
        data = self.cleaned_data["workloads"]
        specs = []
        for opt in data:
            parts = opt.split(":", 1)
            if len(parts) == 2:
                specs.append((parts[0], parts[1]))
            else:
                specs.append(("", parts[0]))
        return specs

    def clean_tags(self):
        # override base class validation
        return self.cleaned_data["tags"]

    def clean_arch(self):
        # override base class validation
        return self.cleaned_data["arch"]

    def clean_zone(self):
        # override base class validation
        return self.cleaned_data["zone"]

    def clean_not_in_zone(self):
        # override base class validation
        return self.cleaned_data["not_in_zone"]

    def clean_pool(self):
        # override base class validation
        return self.cleaned_data["pool"]

    def clean_not_in_pool(self):
        # override base class validation
        return self.cleaned_data["not_in_pool"]

    def clean_vlans(self):
        # override base class validation
        return self.cleaned_data.get("vlans")

    def clean_not_vlans(self):
        # override base class validation
        return self.cleaned_data["not_vlans"]

    def clean_subnets(self):
        # override base class validation
        return self.cleaned_data.get("subnets")

    def clean_not_subnets(self):
        # override base class validation
        return self.cleaned_data["not_subnets"]

    def clean_owner(self):
        # override base class validation
        return self.cleaned_data["owner"]

    def clean_interfaces(self):
        values = self.cleaned_data["interfaces"]
        specifiers = []
        for val in values:
            opts = []
            for constraint in val.split(","):
                key, val = constraint.split("=", 1)
                if key not in NETWORKING_CONSTRAINT_NAMES:
                    raise ValidationError(
                        "Unknown interfaces constraint: '%s" % key
                    )
                opts.append(f"{key}:{val}")
            specifiers.append("&&".join(opts))
        return specifiers

    def filter_by_interfaces(self, filtered_nodes):
        specifiers = self.cleaned_data.get("interfaces")
        node_ids = set()
        for spec in specifiers:
            new_node_ids, _ = Interface.objects.get_matching_node_map(spec)
            node_ids.update(new_node_ids)
        if len(node_ids) > 0:
            filtered_nodes = filtered_nodes.filter(id__in=node_ids)
        return {}, filtered_nodes

    def clean_devices(self):
        values = self.cleaned_data["devices"]
        specifiers = []
        for val in values:
            opts = []
            for constraint in val.split(","):
                key, val = constraint.split("=", 1)
                if key not in DEVICE_CONSTRAINT_NAMES:
                    raise ValidationError(
                        "Unknown devices constraint: '%s" % key
                    )
                opts.append(tuple((key, val)))
            specifiers.append(opts)
        return specifiers

    def filter_by_devices(self, filtered_nodes):
        FIELD = "current_config__nodedevice"
        specifiers = self.cleaned_data.get("devices")
        for spec in specifiers:
            query = Q()
            for key, value in spec:
                if value.startswith("="):
                    query |= Q(**{f"{FIELD}__{key}__exact": value[1:]})
                else:
                    query |= Q(**{f"{FIELD}__{key}__icontains": value})
            filtered_nodes = filtered_nodes.filter(query)
        return filtered_nodes

    def clean_storage(self):
        values = self.cleaned_data["storage"]
        constraints = []
        for val in values:
            storage = storage_validator(val)
            if storage:
                constraints.extend(
                    [
                        (
                            int(float(size) * (1000**3)),
                            tags.split(",") if tags != "" else [],
                        )
                        for (_, size, tags) in storage
                    ]
                )
        return constraints

    def filter_by_storage(self, filtered_nodes):
        storage = self.cleaned_data.get("storage")
        node_ids = []
        for size, tags in storage:
            if "partition" in tags:
                part_tags = list(tags)
                part_tags.remove("partition")
                parts = Partition.objects.filter(size__gte=size)
                if part_tags:
                    parts = parts.filter(tags__contains=part_tags)
                node_ids.extend(
                    list(
                        parts.order_by().values_list(
                            "partition_table__block_device__node_config__node_id",
                            flat=True,
                        )
                    )
                )
            else:
                devs = BlockDevice.objects.filter(size__gte=size)
                if tags is not None:
                    devs = devs.filter(tags__contains=tags)
                node_ids.extend(
                    list(
                        devs.order_by().values_list(
                            "node_config__node_id", flat=True
                        )
                    )
                )
        if node_ids:
            filtered_nodes = filtered_nodes.filter(id__in=node_ids)
        return {}, filtered_nodes

    def _free_text_search(self, nodes):
        data = self.cleaned_data.get("free_text")
        for txt in data:
            subq = Q()
            for field in (
                "distro_series",
                "fabric_name",
                "fqdn",
                "osystem",
                "owner",
                "pod_type",
                "pod",
                "spaces",
                "pool",
                "pxe_mac",
                "tags",
                "workloads",
                "zone",
            ):
                (db_field, cond) = self.FREETEXT_FILTERS[field]
                subq = reduce(
                    lambda q, c: q.__or__(c),
                    cond(db_field, [txt]),
                    subq,
                )
            nodes = nodes.filter(subq)
        return nodes

    def _apply_filters(self, nodes):
        nodes = super()._apply_filters(nodes)
        nodes = self._free_text_search(nodes)
        return nodes.distinct()
