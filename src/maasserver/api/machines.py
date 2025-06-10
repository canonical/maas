# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "AnonMachinesHandler",
    "MachineHandler",
    "MachinesHandler",
    "get_storage_layout_params",
]

from collections import namedtuple
import json
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
)
from django.urls import reverse
from formencode import validators
from formencode.validators import Int, StringBool
from piston3.models import Token
from piston3.utils import rc
import yaml

from maascommon.fields import MAC_FIELD_RE
from maasserver import locks
from maasserver.api.logger import maaslog
from maasserver.api.nodes import (
    AnonNodeHandler,
    AnonNodesHandler,
    NodeHandler,
    NodesHandler,
    PowerMixin,
    PowersMixin,
    WorkloadAnnotationsMixin,
)
from maasserver.api.support import admin_method, operation
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_list,
    get_optional_param,
)
from maasserver.clusterrpc.driver_parameters import get_all_power_types
from maasserver.enum import (
    BMC_TYPE,
    BRIDGE_TYPE,
    BRIDGE_TYPE_CHOICES,
    BRIDGE_TYPE_CHOICES_DICT,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIForbidden,
    MAASAPIValidationError,
    NodesNotAvailable,
    NodeStateViolation,
    Unauthorized,
)
from maasserver.forms import (
    AdminMachineForm,
    get_machine_create_form,
    get_machine_edit_form,
    MachineForm,
)
from maasserver.forms.clone import CloneForm
from maasserver.forms.ephemeral import CommissionForm, ReleaseForm
from maasserver.forms.filesystem import (
    MountNonStorageFilesystemForm,
    UnmountNonStorageFilesystemForm,
)
from maasserver.forms.pods import ComposeMachineForPodsForm
from maasserver.models import (
    Config,
    Domain,
    Interface,
    Machine,
    NodeMetadata,
    PhysicalBlockDevice,
    Pod,
    RackController,
    VirtualBlockDevice,
)
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.node_constraint_filter_forms import (
    AcquireNodeForm,
    nodes_by_interface,
    nodes_by_storage,
)
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.permissions import NodePermission, PodPermission
from maasserver.preseed import get_curtin_merged_config
from maasserver.storage_layouts import (
    StorageLayoutError,
    StorageLayoutForm,
    StorageLayoutMissingBootDiskError,
)
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.orm import get_first, reload_object

# NUMANodeHugepages fields exposed in the API.
DISPLAYED_NUMANODEHUGEPAGES_FIELDS = ("total", "page_size")

# NUMANode fields exposed in the API.
DISPLAYED_NUMANODE_FIELDS = (
    "index",
    "cores",
    "memory",
    ("hugepages_set", DISPLAYED_NUMANODEHUGEPAGES_FIELDS),
)


# Machine's fields exposed on the API.
DISPLAYED_MACHINE_FIELDS = (
    "system_id",
    "hostname",
    "description",
    "hardware_uuid",
    "domain",
    "fqdn",
    "owner",
    "owner_data",
    "locked",
    "cache_sets",
    "bcaches",
    "bios_boot_method",
    "boot_interface",
    "architecture",
    "min_hwe_kernel",
    "hwe_kernel",
    "cpu_count",
    "cpu_speed",
    "memory",
    "swap_size",
    "storage",
    "status",
    "osystem",
    "distro_series",
    "ephemeral_deploy",
    "error_description",
    "netboot",
    "power_type",
    "power_state",
    "tag_names",
    "address_ttl",
    "ip_addresses",
    "interface_set",
    "zone",
    "pool",
    "disable_ipv4",
    "constraints_by_type",
    "boot_disk",
    "blockdevice_set",
    "physicalblockdevice_set",
    "virtualblockdevice_set",
    "volume_groups",
    "raids",
    "status_action",
    "status_message",
    "status_name",
    "node_type",
    "node_type_name",
    "special_filesystems",
    "parent",
    "pod",
    "default_gateways",
    "current_commissioning_result_id",
    "current_testing_result_id",
    "current_installation_result_id",
    "commissioning_status",
    "commissioning_status_name",
    "testing_status",
    "testing_status_name",
    "cpu_test_status",
    "cpu_test_status_name",
    "memory_test_status",
    "memory_test_status_name",
    "network_test_status",
    "network_test_status_name",
    "storage_test_status",
    "storage_test_status_name",
    "other_test_status",
    "other_test_status_name",
    "hardware_info",
    "interface_test_status",
    "interface_test_status_name",
    ("numanode_set", DISPLAYED_NUMANODE_FIELDS),
    "virtualmachine_id",
    "workload_annotations",
    "last_sync",
    "sync_interval",
    "next_sync",
    "enable_hw_sync",
    "enable_kernel_crash_dump",
    "is_dpu",
)

# Limited set of machine fields exposed on the anonymous API.
DISPLAYED_ANON_MACHINE_FIELDS = (
    "system_id",
    "hostname",
    "domain",
    "fqdn",
    "architecture",
    "status",
    "power_type",
    "power_state",
    "zone",
    "status_action",
    "status_message",
    "status_name",
    "node_type",
)


AllocationOptions = namedtuple(
    "AllocationOptions",
    (
        "agent_name",
        "bridge_all",
        "bridge_type",
        "bridge_fd",
        "bridge_stp",
        "comment",
        "install_rackd",
        "install_kvm",
        "register_vmhost",
        "ephemeral_deploy",
        "enable_hw_sync",
    ),
)


def get_storage_layout_params(request, required=False, extract_params=False):
    """Return and validate the storage_layout parameter."""
    form = StorageLayoutForm(required=required, data=request.data)
    if not form.is_valid():
        raise MAASAPIValidationError(form.errors)
    # The request data needs to be mutable so replace the immutable QueryDict
    # with a mutable one.
    request.data = request.data.copy()
    storage_layout = request.data.pop("storage_layout", None)
    if not storage_layout:
        storage_layout = None
    else:
        storage_layout = storage_layout[0]
    params = {}
    # Grab all the storage layout parameters.
    if extract_params:
        for key, value in request.data.items():
            if key.startswith("storage_layout_"):
                params[key.replace("storage_layout_", "")] = value
        # Remove the storage_layout_ parameters from the request.
        for key in params:
            request.data.pop("storage_layout_%s" % key)
    return storage_layout, params


def get_allocation_options(request) -> AllocationOptions:
    """Parses optional parameters for allocation and deployment."""
    comment = get_optional_param(request.POST, "comment")
    default_bridge_all = False
    install_rackd = get_optional_param(
        request.POST, "install_rackd", default=False, validator=StringBool
    )
    install_kvm = get_optional_param(
        request.POST, "install_kvm", default=False, validator=StringBool
    )
    register_vmhost = get_optional_param(
        request.POST, "register_vmhost", default=False, validator=StringBool
    )
    ephemeral_deploy = get_optional_param(
        request.POST, "ephemeral_deploy", default=False, validator=StringBool
    )
    if (install_kvm or register_vmhost) and not ephemeral_deploy:
        default_bridge_all = True
    bridge_all = get_optional_param(
        request.POST,
        "bridge_all",
        default=default_bridge_all,
        validator=StringBool,
    )
    bridge_type = get_optional_param(
        request.POST, "bridge_type", default=BRIDGE_TYPE.STANDARD
    )
    if bridge_type not in BRIDGE_TYPE_CHOICES_DICT:
        raise MAASAPIValidationError(
            {
                "bridge_type": compose_invalid_choice_text(
                    "bridge_type", BRIDGE_TYPE_CHOICES
                )
            }
        )
    bridge_stp = get_optional_param(
        request.POST, "bridge_stp", default=False, validator=StringBool
    )
    bridge_fd = get_optional_param(
        request.POST, "bridge_fd", default=0, validator=Int
    )

    enable_hw_sync = get_optional_param(
        request.POST, "enable_hw_sync", default=False, validator=StringBool
    )

    agent_name = request.data.get("agent_name", "")
    return AllocationOptions(
        agent_name,
        bridge_all,
        bridge_type,
        bridge_fd,
        bridge_stp,
        comment,
        install_rackd,
        install_kvm,
        register_vmhost,
        ephemeral_deploy,
        enable_hw_sync,
    )


def get_allocated_composed_machine(
    request, data, storage, interfaces, pods, form, input_constraints
):
    """Return composed machine if input constraints are matched."""
    machine = None
    # Gather tags and not_tags.
    tags = None
    not_tags = None
    for name, value in input_constraints:
        if name == "tags":
            tags = value
        elif name == "not_tags":
            not_tags = value

    if tags:
        pods = pods.filter(tags__contains=tags)
    if not_tags:
        pods = pods.exclude(tags__contains=not_tags)
    if form.cleaned_data.get("pod"):
        pods = pods.filter(name__in=form.cleaned_data.get("pod"))
    if form.cleaned_data.get("pod_type"):
        pods = pods.filter(power_type__in=form.cleaned_data.get("pod_type"))
    if form.cleaned_data.get("not_pod"):
        pods = pods.exclude(name__in=form.cleaned_data.get("not_pod"))
    if form.cleaned_data.get("not_pod_type"):
        pods = pods.exclude(
            power_type__in=form.cleaned_data.get("not_pod_type")
        )
    compose_form = ComposeMachineForPodsForm(
        request=request, data=data, pods=pods
    )
    if compose_form.is_valid():
        machine = compose_form.compose()
        if machine is not None:
            # Set the storage variable so the constraint_map is
            # set correct for the composed machine.
            storage = nodes_by_storage(storage, node_ids=[machine.id])
            if storage is None:
                storage = {}
            if interfaces:
                result = nodes_by_interface(
                    interfaces,
                    include_filter=dict(node_config__node_id=machine.id),
                )
                interfaces = result.label_map
            else:
                interfaces = {}
    return machine, storage, interfaces


class MachineHandler(NodeHandler, WorkloadAnnotationsMixin, PowerMixin):
    """
    Manage an individual machine.

    A machine is identified by its system_id.
    """

    api_doc_section_name = "Machine"

    model = Machine
    fields = DISPLAYED_MACHINE_FIELDS

    def delete(self, request, system_id):
        """@description-title Delete a machine
        @description Deletes a machine with the given system_id.

        Note: A machine cannot be deleted if it hosts pod virtual machines.
        Use ``force`` to override this behavior. Forcing deletion will also
        remove hosted pods. E.g. ``/machines/abc123/?force=1``.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "204" 204

        @error (http-status-code) "400" 400
        @error (content) "no-delete" The machine cannot be deleted.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to delete
        this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested static-route is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        node.as_self().delete(
            force=get_optional_param(request.GET, "force", False, StringBool)
        )
        return rc.DELETED

    @classmethod
    def boot_disk(handler, machine):
        """Return the boot_disk for the machine."""
        return machine.get_boot_disk()

    @classmethod
    def boot_interface(handler, machine):
        """The network interface which is used to boot over the network."""
        return machine.get_boot_interface()

    @classmethod
    def parent(handler, machine):
        """The parent machine this machine is child to."""
        parent = machine.parent
        if parent is not None:
            return {
                "system_id": parent.system_id,
                "resource_uri": reverse(
                    "machine_handler", args=[parent.system_id]
                ),
                "__incomplete__": True,
            }

    @classmethod
    def pod(handler, machine):
        """The pod this machine is part of."""
        bmc = machine.bmc
        if bmc is None:
            return None
        elif bmc.bmc_type == BMC_TYPE.POD:
            return {
                "id": bmc.id,
                "name": bmc.name,
                "resource_uri": reverse("pod_handler", kwargs={"id": bmc.id}),
            }
        else:
            return None

    @classmethod
    def blockdevice_set(handler, machine):
        return [
            block_device.actual_instance
            for block_device in machine.current_config.blockdevice_set.all()
        ]

    @classmethod
    def physicalblockdevice_set(handler, machine):
        """Use precached queries instead of attribute on the object."""
        return [
            block_device.actual_instance
            for block_device in machine.current_config.blockdevice_set.all()
            if isinstance(block_device.actual_instance, PhysicalBlockDevice)
        ]

    @classmethod
    def virtualblockdevice_set(handler, machine):
        """Use precached queries instead of attribute on the object."""
        return [
            block_device.actual_instance
            for block_device in machine.current_config.blockdevice_set.all()
            if isinstance(block_device.actual_instance, VirtualBlockDevice)
        ]

    @classmethod
    def _filesystem_groups(handler, machine):
        """Return the `FilesystemGroup` for `machine`."""
        fsgroup = {}
        for block_device in machine.current_config.blockdevice_set.all():
            for filesystem in block_device.filesystem_set.all():
                if filesystem.filesystem_group is not None:
                    fsgroup[filesystem.filesystem_group.id] = (
                        filesystem.filesystem_group
                    )
            for ptable in block_device.partitiontable_set.all():
                for partition in ptable.partitions.all():
                    for filesystem in partition.filesystem_set.all():
                        if filesystem.filesystem_group is not None:
                            fsgroup[filesystem.filesystem_group.id] = (
                                filesystem.filesystem_group
                            )
        return fsgroup.values()

    @classmethod
    def volume_groups(handler, machine):
        """Return the volume groups on this machine."""
        return [
            {
                "system_id": machine.system_id,
                "id": fsgroup.id,
                "__incomplete__": True,
            }
            for fsgroup in handler._filesystem_groups(machine)
            if fsgroup.is_lvm()
        ]

    @classmethod
    def raids(handler, machine):
        """Return the raids on this machine."""
        return [
            {
                "system_id": machine.system_id,
                "id": fsgroup.id,
                "__incomplete__": True,
            }
            for fsgroup in handler._filesystem_groups(machine)
            if fsgroup.is_raid()
        ]

    @classmethod
    def cache_sets(handler, machine):
        """Return the cache sets on this machine."""
        sets = {}
        for block_device in machine.current_config.blockdevice_set.all():
            for filesystem in block_device.filesystem_set.all():
                if filesystem.cache_set is not None:
                    sets[filesystem.cache_set.id] = filesystem.cache_set
            for ptable in block_device.partitiontable_set.all():
                for partition in ptable.partitions.all():
                    for filesystem in partition.filesystem_set.all():
                        if filesystem.cache_set is not None:
                            sets[filesystem.cache_set.id] = (
                                filesystem.cache_set
                            )
        return [
            {
                "system_id": machine.system_id,
                "id": cacheset_id,
                "__incomplete__": True,
            }
            for cacheset_id in sets
        ]

    @classmethod
    def bcaches(handler, machine):
        """Return the bcaches on this machine."""
        return [
            {
                "system_id": machine.system_id,
                "id": fsgroup.id,
                "__incomplete__": True,
            }
            for fsgroup in handler._filesystem_groups(machine)
            if fsgroup.is_bcache()
        ]

    @classmethod
    def default_gateways(handler, machine):
        """The default gateways that will be used for this machine."""
        gateways = machine.get_default_gateways()
        ipv4 = gateways.ipv4.gateway_ip if gateways.ipv4 is not None else None
        ipv6 = gateways.ipv6.gateway_ip if gateways.ipv6 is not None else None
        return {
            "ipv4": {
                "gateway_ip": ipv4,
                "link_id": machine.gateway_link_ipv4_id,
            },
            "ipv6": {
                "gateway_ip": ipv6,
                "link_id": machine.gateway_link_ipv6_id,
            },
        }

    @classmethod
    def virtualmachine_id(handler, machine):
        """The ID of the VirtualMachine associated to this machine, or None."""
        vm = getattr(machine, "virtualmachine", None)
        if vm is None:
            return None
        return vm.id

    def update(self, request, system_id):
        """@description-title Update a machine
        @description Updates a machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "hostname" [required=false] The new hostname for this
        machine.

        @param (string) "description" [required=false] The new description for
        this machine.

        @param (string) "domain" [required=false] The domain for this machine.
        If not given the default domain is used.

        @param (string) "architecture" [required=false] The new architecture
        for this machine.

        @param (string) "min_hwe_kernel" [required=false] A string containing
        the minimum kernel version allowed to be ran on this machine.

        @param (string) "power_type" [required=false] The new power type for
        this machine. If you use the default value, power_parameters will be
        set to the empty string.  Available to admin users.  See the `Power
        types`_ section for a list of the available power types.

        @param (string) "power_parameters_{param1}" [required=false] The new
        value for the 'param1' power parameter.  Note that this is dynamic as
        the available parameters depend on the selected value of the Machine's
        power_type.  Available to admin users. See the `Power types`_ section
        for a list of the available power parameters for each power type.

        @param (boolean) "power_parameters_skip_check" [required=false]
        Whether or not the new power parameters for this machine should be
        checked against the expected power parameters for the machine's power
        type ('true' or 'false').  The default is 'false'.

        @param (string) "pool" [required=false] The resource pool to which the
        machine should belong. All machines belong to the 'default' resource
        pool if they do not belong to any other resource pool.

        @param (string) "zone" [required=false] Name of a valid physical zone
        in which to place this machine.

        @param (string) "swap_size" [required=false] Specifies the size of the
        swap file, in bytes. Field accept K, M, G and T suffixes for values
        expressed respectively in kilobytes, megabytes, gigabytes and
        terabytes.

        @param (boolean) "disable_ipv4" [required=false] Deprecated. If
        specified, must be false.

        @param (int) "cpu_count" [required=false] The amount of CPU cores the
        machine has.

        @param (string) "memory" [required=false] How much memory the machine
        has.  Field accept K, M, G and T suffixes for values expressed
        respectively in kilobytes, megabytes, gigabytes and terabytes.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the updated machine.
        @success-example "success-json" [exkey=machines-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to update
        this machine.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )

        Form = get_machine_edit_form(request.user)
        form = Form(data=request.data, instance=machine)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @classmethod
    def resource_uri(cls, machine=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, machine is a Machine object).
        machine_system_id = "system_id"
        if machine is not None:
            machine_system_id = machine.system_id
        return ("machine_handler", (machine_system_id,))

    @operation(idempotent=True)
    def get_token(self, request, system_id):
        """@description-title Get a machine token

        @param (string) "{system_id}" [required=true] The machines' system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the machine token.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id,
            user=request.user,
            perm=NodePermission.admin_read,
        )

        try:
            token = Token.objects.select_related("consumer").get(
                nodekey__node=node
            )
        except Token.DoesNotExist:
            return None

        return {
            "token_key": token.key,
            "token_secret": token.secret,
            "consumer_key": token.consumer.key,
        }

    @operation(idempotent=False)
    def deploy(self, request, system_id):
        """@description-title Deploy a machine
        @description Deploys an operating system to a machine with the given
        system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "user_data" [required=false] If present, this blob of
        base64-encoded user-data to be made available to the machines through
        the metadata service.

        @param (string) "distro_series" [required=false] If present, this
        parameter specifies the OS release the machine will use. For example
        valid values to deploy Jammy Jellyfish are ``ubuntu/jammy``, ``jammy`` and
        ``ubuntu/22.04``, ``22.04``.
        @param-example "distro_series"
            ubuntu/jammy

        @param (string) "hwe_kernel" [required=false] If present, this
        parameter specified the kernel to be used on the machine

        @param (string) "agent_name" [required=false] An optional agent name to
        attach to the acquired machine.

        @param (boolean) "bridge_all" [required=false] Optionally create a
        bridge interface for every configured interface on the machine. The
        created bridges will be removed once the machine is released.
        (Default: false)

        @param (string) "bridge_type" [required=false] Optionally create the
        bridges with this type. Possible values are: ``standard``, ``ovs``.

        @param (boolean) "bridge_stp" [required=false] Optionally turn spanning
        tree protocol on or off for the bridges created on every configured
        interface.  (Default: false)

        @param (int) "bridge_fd" [required=false] Optionally adjust the forward
        delay to time seconds.  (Default: 15)

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @param (boolean) "install_rackd" [required=false] If true, the rack
        controller will be installed on this machine.

        @param (boolean) "install_kvm" [required=false] If true, KVM will be
        installed on this machine and added to MAAS.

        @param (boolean) "register_vmhost" [required=false] If true, the
        machine will be registered as a LXD VM host in MAAS.

        @param (boolean) "ephemeral_deploy" [required=false] If true, machine
        will be deployed ephemerally even if it has disks.

        @param (boolean) "enable_kernel_crash_dump" [required=false] If true, machine
        will be deployed with the kernel crash dump feature enabled and configured automatically.

        @param (boolean) "vcenter_registration" [required=false] If false, do
        not send globally defined VMware vCenter credentials to the machine.

        @param (boolean) "enable_hw_sync" [required=false] If true, machine
        will be deployed with a small agent periodically pushing hardware data to detect
        any change in devices.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the deployed machine.
        @success-example "success-json" [exkey=machines-deploy] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to deploy
        this machine.

        @error (http-status-code) "503" 503
        @error (content) "no-ips" MAAS attempted to allocate an IP address, and
        there were no IP addresses available on the relevant cluster interface.
        """
        series = request.POST.get("distro_series", None)
        license_key = request.POST.get("license_key", None)
        hwe_kernel = request.POST.get("hwe_kernel", None)
        enable_kernel_crash_dump = request.POST.get(
            "enable_kernel_crash_dump", None
        )
        # Acquiring a node requires EDIT permissions.
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        options = get_allocation_options(request)
        # Deploying a node requires re-checking for EDIT permissions.
        if not request.user.has_perm(NodePermission.edit, machine):
            raise PermissionDenied()
        if options.install_rackd and not request.user.has_perm(
            NodePermission.admin, machine
        ):
            raise PermissionDenied("Only administrators can deploy MAAS racks")
        if (
            options.install_kvm or options.register_vmhost
        ) and not request.user.has_perm(NodePermission.admin, machine):
            raise PermissionDenied("Only administratros can deploy VM hosts")
        ephemeral_deploy = options.ephemeral_deploy or machine.is_diskless
        if (
            options.install_kvm or options.register_vmhost
        ) and ephemeral_deploy:
            raise MAASAPIBadRequest(
                "A machine can not be a VM host if it is deployed to memory."
            )
        if machine.status == NODE_STATUS.READY:
            with locks.node_acquire:
                if machine.owner is not None and machine.owner != request.user:
                    raise NodeStateViolation(
                        "Can't allocate a machine belonging to another user."
                    )
                maaslog.info(
                    "Request from user %s to acquire machine: %s (%s)",
                    request.user.username,
                    machine.fqdn,
                    machine.system_id,
                )
                machine.acquire(
                    request.user,
                    agent_name=options.agent_name,
                    comment=options.comment,
                    bridge_all=options.bridge_all,
                    bridge_type=options.bridge_type,
                    bridge_stp=options.bridge_stp,
                    bridge_fd=options.bridge_fd,
                )
        if NODE_STATUS.DEPLOYING not in NODE_TRANSITIONS[machine.status]:
            raise NodeStateViolation(
                "Can't deploy a machine that is in the '{}' state".format(
                    NODE_STATUS_CHOICES_DICT[machine.status]
                )
            )

        if not series:
            series = Config.objects.get_config("default_distro_series")
        Form = get_machine_edit_form(request.user)
        form = Form(instance=machine, data={})
        form.set_distro_series(series=series)
        if license_key is not None:
            form.set_license_key(license_key=license_key)
        if hwe_kernel is not None:
            form.set_hwe_kernel(hwe_kernel=hwe_kernel)

        form.set_enable_kernel_crash_dump(
            enable_kernel_crash_dump=(
                Config.objects.get_config("enable_kernel_crash_dump")
                if enable_kernel_crash_dump is None
                else enable_kernel_crash_dump
            )
        )
        form.set_install_rackd(install_rackd=options.install_rackd)
        form.set_ephemeral_deploy(ephemeral_deploy=ephemeral_deploy)
        form.set_enable_hw_sync(enable_hw_sync=options.enable_hw_sync)
        if form.is_valid():
            form.save()
        else:
            raise MAASAPIValidationError(form.errors)
        # Check that the curtin preseeds renders correctly
        # if not an ephemeral deployment.
        if not ephemeral_deploy:
            try:
                get_curtin_merged_config(request, machine)
            except Exception as e:
                raise MAASAPIBadRequest("Failed to render preseed: %s" % e)  # noqa: B904

        if machine.osystem == "esxi" and request.user.has_perm(
            NodePermission.admin, machine
        ):
            if get_optional_param(
                request.POST,
                "vcenter_registration",
                default=True,
                validator=StringBool,
            ):
                NodeMetadata.objects.update_or_create(
                    node=machine,
                    key="vcenter_registration",
                    defaults={"value": "True"},
                )
            else:
                NodeMetadata.objects.filter(
                    node=machine, key="vcenter_registration"
                ).delete()

        return self.power_on(request, system_id)

    @operation(idempotent=False)
    def release(self, request, system_id):
        """@description-title Release a machine
        @description Releases a machine with the given system_id. Note that
        this operation is the opposite of allocating a machine.

        **Erasing drives**:

        If neither ``secure_erase`` nor ``quick_erase`` are specified, MAAS
        will overwrite the whole disk with null bytes. This can be very slow.

        If both ``secure_erase`` and ``quick_erase`` are specified and the
        drive does NOT have a secure erase feature, MAAS will behave as if only
        ``quick_erase`` was specified.

        If ``secure_erase`` is specified and ``quick_erase`` is NOT specified
        and the drive does NOT have a secure erase feature, MAAS will behave as
        if ``secure_erase`` was NOT specified, i.e. MAAS will overwrite the
        whole disk with null bytes. This can be very slow.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @param (boolean) "erase" [required=false] Erase the disk when
        releasing.

        @param (boolean) "secure_erase" [required=false] Use the drive's secure
        erase feature if available.  In some cases, this can be much faster
        than overwriting the drive.  Some drives implement secure erasure by
        overwriting themselves so this could still be slow.

        @param (boolean) "quick_erase" [required=false] Wipe 2MiB at the start
        and at the end of the drive to make data recovery inconvenient and
        unlikely to happen by accident. This is not secure.

        @param (boolean) "force" [required=false] Will force the release of a
        machine. If the machine was deployed as a KVM host, this will be
        deleted as well as all machines inside the KVM host. USE WITH CAUTION.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the released machine.
        @success-example "success-json" [exkey=machines-release] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        release this machine.

        @error (http-status-code) "409" 409
        @error (content) "no-release" The machine is in a state that prevents
        it from being released.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        form = ReleaseForm(
            instance=machine, user=request.user, data=request.data
        )
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        if machine.status in (NODE_STATUS.RELEASING, NODE_STATUS.READY):
            # Nothing to do if this machine is already releasing, otherwise
            # this may be a redundant retry, and the
            # postcondition is achieved, so call this success.
            pass
        elif machine.status in RELEASABLE_STATUSES:
            scripts = form.cleaned_data["scripts"]

            params = {}
            if form.cleaned_data["erase"]:
                params["wipe-disks"] = {}
                params["wipe-disks"]["secure_erase"] = form.cleaned_data[
                    "secure_erase"
                ]
                params["wipe-disks"]["quick_erase"] = form.cleaned_data[
                    "quick_erase"
                ]
            params = params | form.get_script_param_dict(scripts)
            machine.start_releasing(
                user=request.user,
                comment=form.cleaned_data["comment"],
                scripts=scripts,
                script_input=params,
                force=form.cleaned_data["force"],
            )
        else:
            raise NodeStateViolation(
                "Machine cannot be released in its current "
                f"state ('{machine.display_status()}')."
            )
        return machine

    @operation(idempotent=False)
    def commission(self, request, system_id):
        """@description-title Commission a machine
        @description Begin commissioning process for a machine.

        A machine in the 'ready', 'declared' or 'failed test' state may
        initiate a commissioning cycle where it is checked out and tested in
        preparation for transitioning to the 'ready' state. If it is already in
        the 'ready' state this is considered a re-commissioning process which
        is useful if commissioning tests were changed after it previously
        commissioned.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (int) "enable_ssh" [required=false]  Whether to enable SSH for
        the commissioning environment using the user's SSH key(s). '1' == True,
        '0' == False.

        @param (int) "skip_bmc_config" [required=false] Whether to skip
        re-configuration of the BMC for IPMI based machines. '1' == True, '0'
        == False.

        @param (int) "skip_networking" [required=false] Whether to skip
        re-configuring the networking on the machine after the commissioning
        has completed. '1' == True, '0' == False.

        @param (int) "skip_storage" [required=false] Whether to skip
        re-configuring the storage on the machine after the commissioning has
        completed. '1' == True, '0' == False.

        @param (string) "commissioning_scripts" [required=false] A comma
        seperated list of commissioning script names and tags to be run. By
        default all custom commissioning scripts are run. Built-in
        commissioning scripts always run. Selecting 'update_firmware' or
        'configure_hba' will run firmware updates or configure HBA's on
        matching machines.

        @param (string) "testing_scripts" [required=false] A comma seperated
        list of testing script names and tags to be run. By default all tests
        tagged 'commissioning' will be run. Set to 'none' to disable running
        tests.

        @param (string) "parameters" [required=false] Scripts selected to run
        may define their own parameters. These parameters may be passed using
        the parameter name. Optionally a parameter may have the script name
        prepended to have that parameter only apply to that specific script.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the commissioning machine.
        @success-example "success-json" [exkey=machines-set-storage]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        form = CommissionForm(
            instance=machine, user=request.user, data=request.data
        )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def set_storage_layout(self, request, system_id):
        """@description-title Change storage layout
        @description Changes the storage layout on machine with the given
        system_id.

        This operation can only be performed on a machine with a status
        of 'Ready'.

        Note: This will clear the current storage layout and any extra
        configuration and replace it will the new layout.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "storage_layout" [required=true] Storage layout for the
        machine: ``flat``, ``lvm``, ``bcache``, ``vmfs6``, ``vmfs7``,
        ``custom`` or ``blank``.

        @param (string) "boot_size" [required=false] Size of the boot partition
        (e.g. 512M, 1G).

        @param (string) "root_size" [required=false] Size of the root partition
        (e.g. 24G).

        @param (string) "root_device" [required=false] Physical block device to
        place the root partition (e.g. /dev/sda).

        @param (string) "vg_name" [required=false] LVM only. Name of created
        volume group.

        @param (string) "lv_name" [required=false] LVM only. Name of created
        logical volume.

        @param (string) "lv_size" [required=false] LVM only.  Size of created
        logical volume.

        @param (string) "cache_device" [required=false] Bcache only. Physical
        block device to use as the cache device (e.g. /dev/sda).

        @param (string) "cache_mode" [required=false] Bcache only. Cache mode
        for bcache device: ``writeback``, ``writethrough``, ``writearound``.

        @param (string) "cache_size" [required=false] Bcache only. Size of the
        cache partition to create on the cache device (e.g. 48G).

        @param (boolean) "cache_no_part" [required=false] Bcache only. Don't
        create a partition on the cache device.  Use the entire disk as the
        cache device.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the machine.
        @success-example "success-json" [exkey=machines-commission] placeholder
        text

        @error (http-status-code) "400" 400
        @error (content) "no-alloc" The requested machine is not allocated.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to set
        the storage layout of this machine.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot change the storage layout on a machine "
                "that is not Ready."
            )
        storage_layout, _ = get_storage_layout_params(request, required=True)
        try:
            machine.set_storage_layout(
                storage_layout, params=request.data, allow_fallback=False
            )
        except StorageLayoutMissingBootDiskError:
            raise MAASAPIBadRequest(  # noqa: B904
                "Machine is missing a boot disk; no storage layout can be "
                "applied."
            )
        except StorageLayoutError as e:
            raise MAASAPIBadRequest(  # noqa: B904
                "Failed to configure storage layout '%s': %s"
                % (storage_layout, str(e))
            )
        return machine

    @classmethod
    def special_filesystems(cls, machine):
        """Render special-purpose filesystems, like tmpfs."""
        return [
            {
                "fstype": filesystem.fstype,
                "label": filesystem.label,
                "uuid": filesystem.uuid,
                "mount_point": filesystem.mount_point,
                "mount_options": filesystem.mount_options,
            }
            for filesystem in machine.get_effective_special_filesystems()
        ]

    @operation(idempotent=False)
    def mount_special(self, request, system_id):
        """@description-title Mount a special-purpose filesystem
        @description Mount a special-purpose filesystem, like tmpfs on a
        machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "fstype" [required=true] The filesystem type. This must
        be a filesystem that does not require a block special device.

        @param (string) "mount_point" [required=true] Path on the filesystem to
        mount.

        @param (string) "mount_option" [required=false] Options to pass to
        mount(8).

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the machine.
        @success-example "success-json" [exkey=machines-mount-special]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to mount
        the special filesystem on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        if machine.status not in {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}:
            raise NodeStateViolation(
                "Cannot mount the filesystem because the machine is not "
                "Ready or Allocated."
            )
        form = MountNonStorageFilesystemForm(machine, data=request.data)
        if form.is_valid():
            # Filesystem is not a first-class object in the Web API, so save
            # it but return the machine.
            form.save()
            return machine
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unmount_special(self, request, system_id):
        """@description-title Unmount a special-purpose filesystem
        @description Unmount a special-purpose filesystem, like tmpfs, on a
        machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "mount_point" [required=true] Path on the filesystem to
        unmount.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the machine.
        @success-example "success-json" [exkey=machines-unmount-special]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        unmount the special filesystem on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        if machine.status not in {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}:
            raise NodeStateViolation(
                "Cannot unmount the filesystem because the machine is not "
                "Ready or Allocated."
            )
        form = UnmountNonStorageFilesystemForm(machine, data=request.data)
        if form.is_valid():
            form.save()  # Returns nothing.
            return machine
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def clear_default_gateways(self, request, system_id):
        """@description-title Clear set default gateways
        @description Clear any set default gateways on a machine with the given
        system_id.

        This will clear both IPv4 and IPv6 gateways on the machine. This will
        transition the logic of identifing the best gateway to MAAS. This logic
        is determined based the following criteria:

        1. Managed subnets over unmanaged subnets.
        2. Bond interfaces over physical interfaces.
        3. Machine's boot interface over all other interfaces except bonds.
        4. Physical interfaces over VLAN interfaces.
        5. Sticky IP links over user reserved IP links.
        6. User reserved IP links over auto IP links.

        If the default gateways need to be specific for this machine you can
        set which interface and subnet's gateway to use when this machine is
        deployed with the `interfaces set-default-gateway` API.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing information
        about the machine.
        @success-example "success-json" [exkey=machines-clear-gateways]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        clear default gateways on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        machine.gateway_link_ipv4 = None
        machine.gateway_link_ipv6 = None
        machine.save()
        return machine

    @operation(idempotent=True)
    def get_curtin_config(self, request, system_id):
        """@description-title Get curtin configuration
        @description Return the rendered curtin configuration for the machine.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the curtin
        configuration.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        see curtin configuration on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        if machine.status not in [
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.FAILED_DEPLOYMENT,
        ]:
            raise MAASAPIBadRequest(
                "Machine %s is not in a deployment state." % machine.hostname
            )
        return HttpResponse(
            yaml.safe_dump(
                get_curtin_merged_config(request, machine),
                default_flow_style=False,
            ),
            content_type="text/plain",
        )

    @operation(idempotent=False)
    def restore_networking_configuration(self, request, system_id):
        """@description-title Restore networking options
        @description Restores networking options to their initial state on a
        machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-restore-networking]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        restore networking options on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        if machine.status not in {
            NODE_STATUS.READY,
            NODE_STATUS.FAILED_TESTING,
        }:
            raise NodeStateViolation(
                "Machine must be in a ready or failed testing state to "
                "restore networking configuration"
            )
        machine.restore_network_interfaces()
        machine.set_initial_networking_configuration()
        return reload_object(machine)

    @operation(idempotent=False)
    def restore_storage_configuration(self, request, system_id):
        """@description-title Restore storage configuration
        @description Restores storage configuration options to their initial
        state on a machine with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-restore-storage]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        restore storage options on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        if machine.status not in {
            NODE_STATUS.READY,
            NODE_STATUS.FAILED_TESTING,
        }:
            raise NodeStateViolation(
                "Machine must be in a ready or failed testing state to "
                "restore storage configuration."
            )
        machine.set_default_storage_layout()
        return reload_object(machine)

    @operation(idempotent=False)
    def restore_default_configuration(self, request, system_id):
        """@description-title Restore default configuration
        @description Restores the default configuration options on a machine
        with the given system_id.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-restore-default]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        restore default options on this machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        if machine.status not in {
            NODE_STATUS.READY,
            NODE_STATUS.FAILED_TESTING,
        }:
            raise NodeStateViolation(
                "Machine must be in a ready or failed testing state to "
                "restore default networking and storage configuration."
            )
        machine.set_default_storage_layout()
        machine.restore_network_interfaces()
        machine.set_initial_networking_configuration()
        return reload_object(machine)

    @operation(idempotent=False)
    def mark_broken(self, request, system_id):
        """@description-title Mark a machine as Broken
        @description Mark a machine with the given system_id as 'Broken'.

        If the node is allocated, release it first.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "comment" [required=false] Optional comment for the
        event log. Will be displayed on the node as an error description until
        marked fixed.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-mark-broken]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        the machine as Broken.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NodePermission.edit
        )
        if node.owner_id != request.user.id:
            raise MAASAPIForbidden()
        comment = get_optional_param(request.POST, "comment")
        if not comment:
            # read old error_description to for backward compatibility
            comment = get_optional_param(request.POST, "error_description")
        node.mark_broken(request.user, comment)
        return node

    @operation(idempotent=False)
    def mark_fixed(self, request, system_id):
        """@description-title Mark a machine as Fixed
        @description Mark a machine with the given system_id as 'Fixed'.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-mark-fixed]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        the machine as Fixed.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        comment = get_optional_param(request.POST, "comment")
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NodePermission.admin
        )
        node.mark_fixed(request.user, comment)
        maaslog.info(
            "%s: User %s marked node as fixed",
            node.hostname,
            request.user.username,
        )
        return node

    @operation(idempotent=False)
    def rescue_mode(self, request, system_id):
        """@description-title Enter rescue mode
        @description Begins the rescue mode process on a machine with the given
        system_id.

        A machine in the 'deployed' or 'broken' state may initiate the
        rescue mode process.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-rescue-mode]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        begin rescue mode on the machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        machine.start_rescue_mode(request.user)
        maaslog.info(
            "%s: User %s started rescue mode.",
            machine.hostname,
            request.user.username,
        )
        return machine

    @operation(idempotent=False)
    def exit_rescue_mode(self, request, system_id):
        """@description-title Exit rescue mode
        @description Exits the rescue mode process on a machine with the given
        system_id.

        A machine in the 'rescue mode' state may exit the rescue mode
        process.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-exit-rescue-mode]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        exit rescue mode on the machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        machine.stop_rescue_mode(request.user)
        maaslog.info(
            "%s: User %s stopped rescue mode.",
            machine.hostname,
            request.user.username,
        )
        return machine

    @operation(idempotent=False)
    def lock(self, request, system_id):
        """@description-title Lock a machine
        @description Mark a machine with the given system_id as 'Locked' to
        prevent changes.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-lock]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        lock the machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.lock
        )
        if machine.locked:
            raise NodeStateViolation("Machine is already locked")
        comment = get_optional_param(request.POST, "comment")
        machine.lock(request.user, comment=comment)
        return machine

    @operation(idempotent=False)
    def unlock(self, request, system_id):
        """@description-title Unlock a machine
        @description Mark a machine with the given system_id as 'Unlocked' to
        allow changes.

        @param (string) "{system_id}" [required=true] The machines's system_id.

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-lock]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        unlock the machine.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.lock
        )
        if not machine.locked:
            raise NodeStateViolation("Machine is not locked")
        comment = get_optional_param(request.POST, "comment")
        machine.unlock(request.user, comment=comment)
        return machine


def fix_architecture(data):
    # For backwards compatibilty reasons, requests may be sent with:
    #     architecture with a '/' in it: use normally
    #     architecture without a '/' and no subarchitecture: assume 'generic'
    #     architecture without a '/' and a subarchitecture: use as specified
    #     architecture with a '/' and a subarchitecture: error
    architecture = data.get("architecture", None)
    subarchitecture = data.get("subarchitecture", None)
    if architecture and "/" in architecture:
        if subarchitecture:
            # Architecture with a '/' and a subarchitecture: error.
            raise MAASAPIValidationError(
                "Subarchitecture cannot be specified twice."
            )
    elif architecture:
        if subarchitecture:
            # Architecture without a '/' and a subarchitecture:
            # use as specified.
            data["architecture"] = "/".join([architecture, subarchitecture])
            del data["subarchitecture"]
        else:
            # Architecture without a '/' and no subarchitecture:
            # assume 'generic'.
            data["architecture"] += "/generic"


def create_machine(request, requires_arch=False):
    """Service an http request to create a machine.

    The machine will be in the New state.

    :param request: The http request for this machine to be created.
    :return: A `Machine`.
    :rtype: :class:`maasserver.models.Machine`.
    :raises: ValidationError
    """
    given_arch = request.data.get("architecture", None)
    given_subarch = request.data.get("subarchitecture", None)
    given_min_hwe_kernel = request.data.get("min_hwe_kernel", None)
    altered_query_data = request.data.copy()
    fix_architecture(altered_query_data)

    hwe_regex = re.compile("(hwe|ga)-.+")
    has_arch_with_hwe = given_arch and hwe_regex.search(given_arch) is not None
    has_subarch_with_hwe = (
        given_subarch and hwe_regex.search(given_subarch) is not None
    )
    if has_arch_with_hwe or has_subarch_with_hwe:
        raise MAASAPIValidationError(
            "hwe kernel must be specified using the min_hwe_kernel argument."
        )

    if given_min_hwe_kernel:
        if hwe_regex.search(given_min_hwe_kernel) is None:
            raise MAASAPIValidationError(
                'min_hwe_kernel must start with "hwe-" or "ga-"'
            )

    Form = get_machine_create_form(request.user)
    form = Form(
        data=altered_query_data, request=request, requires_arch=requires_arch
    )
    if form.is_valid():
        machine = form.save()
        maaslog.info("%s: Enlisted new machine", machine.hostname)
        return machine
    else:
        raise MAASAPIValidationError(form.errors)


class AnonMachineHandler(AnonNodeHandler):
    """Anonymous machine handler.

    Only outputs machine model for anonymous results.
    """

    read = create = update = delete = None
    model = Machine
    fields = DISPLAYED_ANON_MACHINE_FIELDS

    @classmethod
    def resource_uri(cls, machine=None):
        system_id = "system_id" if machine is None else machine.system_id
        return ("machine_handler", (system_id,))


class AnonMachinesHandler(AnonNodesHandler):
    """Anonymous access to Machines."""

    read = update = delete = None
    base_model = Machine

    def _update_new_node(
        self, machine, architecture, power_type, power_parameters
    ):
        """Update a new machine's editable fields.

        Update the power parameters with the new MAAS password and
        ensure the architecture is set.
        """
        if not power_type and not power_parameters:
            Form = MachineForm
            data = {"architecture": architecture}
        else:
            # AdminMachineForm must be used so the power parameters can be
            # validated and updated.
            Form = AdminMachineForm
            data = {
                "architecture": architecture,
                "power_type": power_type,
                "power_parameters": power_parameters,
            }
        fix_architecture(data)

        form = Form(data=data, instance=machine, requires_arch=True)
        if form.is_valid():
            if machine.status == NODE_STATUS.NEW:
                maaslog.info(
                    "%s: Found existing machine, enlisting", machine.hostname
                )
            else:
                maaslog.info(
                    "%s: Found existing machine, commissioning",
                    machine.hostname,
                )
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def create(self, request):
        # Note: this docstring is duplicated below. Be sure to update both.
        """@description-title Create a new machine
        @description Create a new machine.

        description-title Create a new machine re-installs its operating
        system, in the event that it PXE boots. In anonymous enlistment (and
        when the enlistment is done by a non-admin), the machine is held in the
        "New" state for approval by a MAAS admin.

        The minimum data required is:

        architecture=<arch string> (e.g. "i386/generic")
        mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

        @param (string) "architecture" [required=true] A string containing the
        architecture type of the machine. (For example, "i386", or "amd64".) To
        :type architecture: unicode

        @param (string) "min_hwe_kernel" [required=false] A string containing
        the minimum kernel version allowed to be ran on this machine.

        @param (string) "subarchitecture" [required=false] A string containing
        the subarchitecture type of the machine. (For example, "generic" or
        "hwe-t".) To determine the supported subarchitectures, use the
        boot-resources endpoint.

        @param (string) "mac_addresses" [required=true] One or more MAC
        addresses for the machine. To specify more than one MAC address, the
        parameter must be specified twice. (such as "machines new
        mac_addresses=01:02:03:04:05:06 mac_addresses=02:03:04:05:06:07")

        @param (string) "hostname" [required=false] A hostname. If not given,
        one will be generated.

        @param (string) "domain" [required=false] The domain of the machine. If
        not given the default domain is used.

        @param (string) "power_type" [required=false] A power management type,
        if applicable (e.g. "virsh", "ipmi").

        @param (string) "power_parameters_{param}" [required=false] The
        parameter(s) for the power_type.  Note that this is dynamic as the
        available parameters depend on the selected value of the Machine's
        power_type. `Power types`_ section for a list of the available power
        parameters for each power type.

        @param (boolean) "commission" [required=false,formatting=true] Request
        the newly created machine to be created with status set to
        COMMISSIONING. Machines will wait for COMMISSIONING results and not
        time out. After commissioning is complete, machines will still have to
        be accepted by an administrator.

        @param (boolean) "is_dpu" [required=false] Whether the machine is a DPU
        or not. If not provided, the machine is considered a non-DPU machine.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-create]
        placeholder text
        """
        architecture = request.data.get("architecture")
        power_type = request.data.get("power_type")
        power_parameters = request.data.get("power_parameters")
        mac_addresses = request.data.getlist("mac_addresses")
        commission = get_optional_param(
            request.data, "commission", default=False, validator=StringBool
        )
        machine = None

        # BMC enlistment - Check if there is a pre-existing machine within MAAS
        # that has the same BMC as a known node. Currently only IPMI is
        # supported.
        if power_type == "ipmi" and power_parameters:
            params = json.loads(power_parameters)
            machine = Machine.objects.filter(
                status__in=[NODE_STATUS.NEW, NODE_STATUS.COMMISSIONING],
                bmc__power_parameters__power_address=(
                    params.get("power_address", "")
                ),
            ).first()
            if machine is not None:
                maaslog.info(
                    "Updating %s, with %s, %s, %s",
                    machine,
                    architecture,
                    power_type,
                    params.get("power_address", ""),
                )
                machine = self._update_new_node(
                    machine, architecture, power_type, power_parameters
                )

        # MAC enlistment - Check if there is a pre-existing machine within MAAS
        # that has an Interface with one of the given MAC addresses.
        if machine is None and mac_addresses:
            interface = None
            macs_valid = all(
                MAC_FIELD_RE.match(mac_address)
                for mac_address in mac_addresses
            )
            if macs_valid:
                interface = Interface.objects.filter(
                    mac_address__in=mac_addresses,
                    node_config__node__node_type=NODE_TYPE.MACHINE,
                    node_config__node__status__in=[
                        NODE_STATUS.NEW,
                        NODE_STATUS.COMMISSIONING,
                    ],
                ).first()
            if interface is not None:
                machine = self._update_new_node(
                    interface.node_config.node.as_self(),
                    architecture,
                    power_type,
                    power_parameters,
                )

        # If the machine isn't being enlisted by BMC or MAC create a new
        # machine object.
        if machine is None:
            machine = create_machine(request, requires_arch=True)

            if commission:
                # Make sure an enlisting NodeMetadata object exists if the
                # machine is NEW. When commissioning finishes this is how
                # MAAS knows to set the status to NEW instead of READY.
                NodeMetadata.objects.update_or_create(
                    node=machine, key="enlisting", defaults={"value": "True"}
                )

        return machine

    @operation(idempotent=False)
    def accept(self, request):
        """Accept a machine's enlistment: not allowed to anonymous users.

        Always returns 401.
        """
        raise Unauthorized("You must be logged in to accept machines.")

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("machines_handler", [])


class MachinesHandler(NodesHandler, PowersMixin):
    """Manage the collection of all the machines in the MAAS."""

    api_doc_section_name = "Machines"
    anonymous = AnonMachinesHandler
    base_model = Machine
    fields = DISPLAYED_MACHINE_FIELDS

    def create(self, request):
        # Note: this docstring is duplicated above. Be sure to update both.
        """@description-title Create a new machine
        @description Create a new machine.

        Adding a server to MAAS will (by default) cause the machine to
        network boot into an ephemeral environment to collect hardware
        information.

        In anonymous enlistment (and when the enlistment is done by a
        non-admin), the machine is held in the "New" state for approval
        by a MAAS admin.

        The minimum data required is:

        architecture=<arch string> (e.g. "i386/generic")
        mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

        @param (string) "architecture" [required=true] A string containing the
        architecture type of the machine. (For example, "i386", or "amd64".) To
        :type architecture: unicode

        @param (string) "min_hwe_kernel" [required=false] A string containing
        the minimum kernel version allowed to be ran on this machine.

        @param (string) "subarchitecture" [required=false] A string containing
        the subarchitecture type of the machine. (For example, "generic" or
        "hwe-t".) To determine the supported subarchitectures, use the
        boot-resources endpoint.

        @param (string) "mac_addresses" [required=true] One or more MAC
        addresses for the machine. To specify more than one MAC address, the
        parameter must be specified twice. (such as "machines new
        mac_addresses=01:02:03:04:05:06 mac_addresses=02:03:04:05:06:07")

        @param (string) "hostname" [required=false] A hostname. If not given,
        one will be generated.

        @param (string) "description" [required=false] A optional description.

        @param (string) "domain" [required=false] The domain of the machine. If
        not given the default domain is used.

        @param (string) "power_type" [required=false] A power management type,
        if applicable (e.g. "virsh", "ipmi").

        @param (string) "power_parameters_{param}" [required=false] The
        parameter(s) for the power_type.  Note that this is dynamic as the
        available parameters depend on the selected value of the Machine's
        power_type. `Power types`_ section for a list of the available power
        parameters for each power type.

        @param (boolean) "commission" [required=false,formatting=true] Request
        the newly created machine to be created with status set to
        COMMISSIONING. Machines will wait for COMMISSIONING results and not
        time out. Machines created by administrators will be commissioned
        unless set to false.

        @param (boolean) "deployed" [required=false,formatting=true] Request
        the newly created machine to be created with status set to
        DEPLOYED. Setting this to true implies commissioning=false,
        meaning that the machine won't go through the commissioning
        process.

        @param (int) "enable_ssh" [required=false]  Whether to enable SSH for
        the commissioning environment using the user's SSH key(s). '1' == True,
        '0' == False.

        @param (int) "skip_bmc_config" [required=false] Whether to skip
        re-configuration of the BMC for IPMI based machines. '1' == True, '0'
        == False.

        @param (int) "skip_networking" [required=false] Whether to skip
        re-configuring the networking on the machine after the commissioning
        has completed. '1' == True, '0' == False.

        @param (int) "skip_storage" [required=false] Whether to skip
        re-configuring the storage on the machine after the commissioning has
        completed. '1' == True, '0' == False.

        @param (string) "commissioning_scripts" [required=false] A comma
        seperated list of commissioning script names and tags to be run. By
        default all custom commissioning scripts are run. Built-in
        commissioning scripts always run. Selecting 'update_firmware' or
        'configure_hba' will run firmware updates or configure HBA's on
        matching machines.

        @param (boolean) "is_dpu" [required=false] Whether the machine is a DPU
        or not. If not provided, the machine is considered a non-DPU machine.

        @param (string) "testing_scripts" [required=false] A comma seperated
        list of testing script names and tags to be run. By default all tests
        tagged 'commissioning' will be run. Set to 'none' to disable running
        tests.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing the machine
        information.
        @success-example "success-json" [exkey=machines-create]
        placeholder text
        """
        # Only admins are allowed to commission, store the value but remove it
        # from the form.
        commission = get_optional_param(
            request.data, "commission", default=True, validator=StringBool
        )
        deployed = get_optional_param(
            request.data, "deployed", default=False, validator=StringBool
        )
        machine = create_machine(request)
        if request.user.is_superuser and commission and not deployed:
            form = CommissionForm(
                instance=machine, user=request.user, data=request.data
            )
            # Silently ignore errors to prevent 500 errors. The commissioning
            # callbacks have their own logging. This fixes LP:1600328.
            if form.is_valid():
                machine = form.save()

        return machine

    def _check_system_ids_exist(self, system_ids):
        """Check that the requested system_ids actually exist in the DB.

        We don't check if the current user has rights to do anything with them
        yet, just that the strings are valid. If not valid raise a BadRequest
        error.
        """
        if not system_ids:
            return
        existing_machines = self.base_model.objects.filter(
            system_id__in=system_ids
        )
        existing_ids = set(
            existing_machines.values_list("system_id", flat=True)
        )
        unknown_ids = system_ids - existing_ids
        if len(unknown_ids) > 0:
            raise MAASAPIBadRequest(
                "Unknown machine(s): %s." % ", ".join(unknown_ids)
            )

    @operation(idempotent=False)
    def accept(self, request):
        """@description-title Accept declared machines
        @description Accept declared machines into MAAS.

        Machines can be enlisted in the MAAS anonymously or by non-admin users,
        as opposed to by an admin.  These machines are held in the New
        state; a MAAS admin must first verify the authenticity of these
        enlistments, and accept them.

        Enlistments can be accepted en masse, by passing multiple machines to
        this call.  Accepting an already accepted machine is not an error, but
        accepting one that is already allocated, broken, etc. is.

        @param (string) "machines" [required=false] A list of system_ids of the
        machines whose enlistment is to be accepted. (An empty list is
        acceptable).

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        accepted machines.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text

        @error (http-status-code) "400" 400
        @error (content) "not-found" One or more of the given machines is not
        found.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to accept
        machines.
        """
        system_ids = set(request.POST.getlist("machines"))
        # Check the existence of these machines first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        machines = self.base_model.objects.get_nodes(
            request.user, perm=NodePermission.admin, ids=system_ids
        )
        if len(machines) < len(system_ids):
            permitted_ids = {machine.system_id for machine in machines}
            raise PermissionDenied(
                "You don't have the required permission to accept the "
                "following machine(s): %s."
                % (", ".join(system_ids - permitted_ids))
            )
        machines = (
            machine.accept_enlistment(request.user) for machine in machines
        )
        return [machine for machine in machines if machine is not None]

    @operation(idempotent=False)
    def accept_all(self, request):
        """@description-title Accept all declared machines
        @description Accept all declared machines into MAAS.

        Machines can be enlisted in the MAAS anonymously or by non-admin users,
        as opposed to by an admin.  These machines are held in the New
        state; a MAAS admin must first verify the authenticity of these
        enlistments, and accept them.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        accepted machines.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text
        """
        machines = self.base_model.objects.get_nodes(
            request.user, perm=NodePermission.admin
        )
        machines = machines.filter(status=NODE_STATUS.NEW)
        machines = (
            machine.accept_enlistment(request.user) for machine in machines
        )
        return [machine for machine in machines if machine is not None]

    @operation(idempotent=False)
    def release(self, request):
        """@description-title Release machines
        @description Release multiple machines. Places the machines back into
        the pool, ready to be reallocated.

        @param (string) "machines" [required=true] A list of system_ids of the
        machines which are to be released.  (An empty list is acceptable).

        @param (string) "comment" [required=false] Optional comment for the
        event log.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        release machines.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text

        @error (http-status-code) "400" 400
        @error (content) "not-found" One or more of the given machines is not
        found.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        release machines.

        @error (http-status-code) "409" 409
        @error (content) "no-release" The current state of the machine prevents
        it from being released.
        """
        system_ids = set(request.POST.getlist("machines"))
        comment = get_optional_param(request.POST, "comment")
        # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        machines = self.base_model.objects.get_nodes(
            request.user, perm=NodePermission.edit, ids=system_ids
        )
        if len(machines) < len(system_ids):
            permitted_ids = {machine.system_id for machine in machines}
            raise PermissionDenied(
                "You don't have the required permission to release the "
                "following machine(s): %s."
                % (", ".join(system_ids - permitted_ids))
            )

        released_ids = []
        failed = []
        for machine in machines:
            if machine.status == NODE_STATUS.READY:
                # Nothing to do.
                pass
            elif machine.status in RELEASABLE_STATUSES:
                machine.start_releasing(
                    user=request.user,
                    comment=comment,
                )
                released_ids.append(machine.system_id)
            else:
                failed.append(
                    f"{machine.system_id} ('{machine.display_status()}')"
                )

        if any(failed):
            raise NodeStateViolation(
                "Machine(s) cannot be released in their current state: %s."
                % ", ".join(failed)
            )
        return released_ids

    @operation(idempotent=True)
    def list_allocated(self, request):
        """@description-title List allocated
        @description List machines that were allocated to the User.

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a list of
        allocated machines.
        @success-example "success-json" [exkey=machines-placeholder]
        placeholder text
        """
        # limit to machines that the user can view
        machines = Machine.objects.get_nodes(request.user, NodePermission.view)
        machines = machines.filter(
            owner=request.user, status=NODE_STATUS.ALLOCATED
        )
        system_ids = get_optional_list(request.GET, "id")
        if system_ids:
            machines = machines.filter(system_id__in=system_ids)
        return machines.order_by("id")

    @operation(idempotent=False)
    def allocate(self, request):
        """@description-title Allocate a machine
        @description Allocates an available machine for deployment.

        Constraints parameters can be used to allocate a machine that possesses
        certain characteristics.  All the constraints are optional and when
        multiple constraints are provided, they are combined using 'AND'
        semantics.

        @param (string) "name" [required=false] Hostname or FQDN of the desired
        machine. If a FQDN is specified, both the domain and the hostname
        portions must match.

        @param (string) "system_id" [required=false] system_id of the desired
        machine.

        @param (string) "arch" [required=false,formatting=true] Architecture of
        the returned machine (e.g. 'i386/generic', 'amd64', 'armhf/highbank',
        etc.).

        If multiple architectures are specified, the machine to acquire may
        match any of the given architectures. To request multiple
        architectures, this parameter must be repeated in the request with each
        value.

        @param (int) "cpu_count" [required=false,formatting=true] Minimum
        number of CPUs a returned machine must have.

        A machine with additional CPUs may be allocated if there is no exact
        match, or if the 'mem' constraint is not also specified.

        @param (int) "mem" [required=false] The minimum amount of memory
        (expressed in MB) the returned machine must have. A machine with
        additional memory may be allocated if there is no exact match, or the
        'cpu_count' constraint is not also specified.

        @param (string) "tags" [required=false,formatting=true] Tags the
        machine must match in order to be acquired.

        If multiple tag names are specified, the machine must be tagged with
        all of them. To request multiple tags, this parameter must be repeated
        in the request with each value.

        @param (string) "not_tags" [required=false] Tags the machine must NOT
        match. If multiple tag names are specified, the machine must NOT be
        tagged with ANY of them. To request exclusion of multiple tags, this
        parameter must be repeated in the request with each value.

        @param (string) "zone" [required=false] Physical zone name the machine
        must be located in.

        @param (string) "not_in_zone" [required=false] List of physical zones
        from which the machine must not be acquired.  If multiple zones are
        specified, the machine must NOT be associated with ANY of them. To
        request multiple zones to exclude, this parameter must be repeated in
        the request with each value.

        @param (string) "pool" [required=false] Resource pool name the machine
        must belong to.

        @param (string) "not_in_pool" [required=false] List of resource pool
        from which the machine must not be acquired. If multiple pools are
        specified, the machine must NOT be associated with ANY of them. To
        request multiple pools to exclude, this parameter must be repeated in
        the request with each value.

        @param (string) "pod" [required=false] Pod the machine must be located
        in.

        @param (string) "not_pod" [required=false] Pod the machine must not be
        located in.

        @param (string) "pod_type" [required=false] Pod type the machine must
        be located in.

        @param (string) "not_pod_type" [required=false] Pod type the machine
        must not be located in.

        @param (string) "subnets" [required=false,formatting=true] Subnets that
        must be linked to the machine.

        "Linked to" means the node must be configured to acquire an address in
        the specified subnet, have a static IP address in the specified subnet,
        or have been observed to DHCP from the specified subnet during
        commissioning time (which implies that it *could* have an address on
        the specified subnet).

        Subnets can be specified by one of the following criteria:

        - <id>: Match the subnet by its 'id' field
        - fabric:<fabric-spec>: Match all subnets in a given fabric.
        - ip:<ip-address>: Match the subnet containing <ip-address> with the
          with the longest-prefix match.
        - name:<subnet-name>: Match a subnet with the given name.
        - space:<space-spec>: Match all subnets in a given space.
        - vid:<vid-integer>: Match a subnet on a VLAN with the specified VID.
          Valid values range from 0 through 4094 (inclusive). An untagged VLAN
          can be specified by using the value "0".
        - vlan:<vlan-spec>: Match all subnets on the given VLAN.

        Note that (as of this writing), the 'fabric', 'space', 'vid', and
        'vlan' specifiers are only useful for the 'not_spaces' version of this
        constraint, because they will most likely force the query to match ALL
        the subnets in each fabric, space, or VLAN, and thus not return any
        nodes. (This is not a particularly useful behavior, so may be changed
        in the future.)

        If multiple subnets are specified, the machine must be associated with
        all of them. To request multiple subnets, this parameter must be
        repeated in the request with each value.

        Note that this replaces the legacy 'networks' constraint in MAAS 1.x.

        @param (string) "not_subnets" [required=false,formatting=true] Subnets
        that must NOT be linked to the machine.

        See the 'subnets' constraint documentation above for more information
        about how each subnet can be specified.

        If multiple subnets are specified, the machine must NOT be associated
        with ANY of them. To request multiple subnets to exclude, this
        parameter must be repeated in the request with each value. (Or a
        fabric, space, or VLAN specifier may be used to match multiple
        subnets).

        Note that this replaces the legacy 'not_networks' constraint in MAAS
        1.x.

        @param (string) "storage" [required=false] A list of storage constraint
        identifiers, in the form: ``label:size(tag[,tag[,...])][,label:...]``.

        @param (string) "interfaces" [required=false,formatting=true] A labeled
        constraint map associating constraint labels with interface properties
        that should be matched. Returned nodes must have one or more interface
        matching the specified constraints. The labeled constraint map must be
        in the format: ``label:key=value[,key2=value2[,...]]``.

        Each key can be one of the following:

        - ``id``: Matches an interface with the specific id
        - ``fabric``: Matches an interface attached to the specified fabric.
        - ``fabric_class``: Matches an interface attached to a fabric with the
          specified class.
        - ``ip``: Matches an interface with the specified IP address assigned
          to it.
        - ``mode``: Matches an interface with the specified mode. (Currently,
          the only supported mode is "unconfigured".)
        - ``name``: Matches an interface with the specified name.  (For
          example, "eth0".)
        - ``hostname``: Matches an interface attached to the node with the
          specified hostname.
        - ``subnet``: Matches an interface attached to the specified subnet.
        - ``space``: Matches an interface attached to the specified space.
        - ``subnet_cidr``: Matches an interface attached to the specified
          subnet CIDR. (For example, "192.168.0.0/24".)
        - ``type``: Matches an interface of the specified type. (Valid types:
          "physical", "vlan", "bond", "bridge", or "unknown".)
        - ``vlan``: Matches an interface on the specified VLAN.
        - ``vid``: Matches an interface on a VLAN with the specified VID.
        - ``tag``: Matches an interface tagged with the specified tag.
        - ``link_speed``: Matches an interface with link_speed equal to or
          greater than the specified speed.

        @param (string) "fabrics" [required=false] Set of fabrics that the
        machine must be associated with in order to be acquired. If multiple
        fabrics names are specified, the machine can be in any of the specified
        fabrics. To request multiple possible fabrics to match, this parameter
        must be repeated in the request with each value.

        @param (string) "not_fabrics" [required=false] Fabrics the machine must
        NOT be associated with in order to be acquired. If multiple fabrics
        names are specified, the machine must NOT be in ANY of them. To request
        exclusion of multiple fabrics, this parameter must be repeated in the
        request with each value.

        @param (string) "fabric_classes" [required=false] Set of fabric class
        types whose fabrics the machine must be associated with in order to be
        acquired. If multiple fabrics class types are specified, the machine
        can be in any matching fabric. To request multiple possible fabrics
        class types to match, this parameter must be repeated in the request
        with each value.

        @param (string) "not_fabric_classes" [required=false] Fabric class
        types whose fabrics the machine must NOT be associated with in order to
        be acquired. If multiple fabrics names are specified, the machine must
        NOT be in ANY of them. To request exclusion of multiple fabrics, this
        parameter must be repeated in the request with each value.

        @param (string) "agent_name" [required=false] An optional agent name to
        attach to the acquired machine.

        @param (string) "comment" [required=false] Comment for the event log.

        @param (boolean) "bridge_all" [required=false] Optionally create a
        bridge interface for every configured interface on the machine. The
        created bridges will be removed once the machine is released.
        (Default: False)

        @param (boolean) "bridge_stp" [required=false] Optionally turn spanning
        tree protocol on or off for the bridges created on every configured
        interface.  (Default: off)

        @param (int) "bridge_fd" [required=false] Optionally adjust the forward
        delay to time seconds.  (Default: 15)

        @param (string) "devices": [required=false] Only return a node which
        have one or more devices containing the following constraints in the
        format key=value[,key2=value2[,...]]

        Each key can be one of the following:

        - ``vendor_id``: The device vendor id
        - ``product_id``: The device product id
        - ``vendor_name``: The device vendor name, not case sensative
        - ``product_name``: The device product name, not case sensative
        - ``commissioning_driver``: The device uses this driver during
          commissioning.

        @param (boolean) "dry_run" [required=false] Optional boolean to
        indicate that the machine should not actually be acquired (this is for
        support/troubleshooting, or users who want to see which machine would
        match a constraint, without acquiring a machine). Defaults to False.

        @param (boolean) "verbose" [required=false] Optional boolean to
        indicate that the user would like additional verbosity in the
        constraints_by_type field (each constraint will be prefixed by
        ``verbose_``, and contain the full data structure that indicates which
        machine(s) matched).

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON object containing a newly
        allocated machine object.
        @success-example "success-json" [exkey=machines-allocate]
        placeholder text

        @error (http-status-code) "409" 409
        @error (content) "no-match" No machine matching the given constraints
        could be found.
        """
        form = AcquireNodeForm(data=request.data)
        # XXX AndresRodriguez 2016-10-27: If new params are added and are not
        # constraints, these need to be added to IGNORED_FIELDS in
        # src/maasserver/node_constraint_filter_forms.py.
        input_constraints = [
            param for param in request.data.lists() if param[0] != "op"
        ]
        maaslog.info(
            "Request from user %s to acquire a machine with constraints: %s",
            request.user.username,
            str(input_constraints),
        )
        options = get_allocation_options(request)
        verbose = get_optional_param(
            request.POST, "verbose", default=False, validator=StringBool
        )
        dry_run = get_optional_param(
            request.POST, "dry_run", default=False, validator=StringBool
        )
        zone = get_optional_param(request.POST, "zone", default=None)

        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        # This lock prevents a machine we've picked as available from
        # becoming unavailable before our transaction commits.
        with locks.node_acquire:
            machines = (
                self.base_model.objects.get_available_machines_for_acquisition(
                    request.user
                )
            )
            machines, storage, interfaces = form.filter_nodes(machines)
            machine = get_first(machines)
            system_id = get_optional_param(
                request.POST, "system_id", default=None
            )
            if machine is None and system_id is None:
                cores = form.cleaned_data.get("cpu_count")
                if cores:
                    cores = int(min(cores))
                memory = form.cleaned_data.get("mem")
                if memory:
                    memory = int(min(memory))
                architecture = None
                architectures = form.cleaned_data.get("arch")
                if architectures is not None:
                    architecture = (
                        None if len(architectures) == 0 else min(architectures)
                    )
                storage = form.cleaned_data.get("storage")
                interfaces = form.cleaned_data.get("interfaces")
                data = {
                    "cores": cores,
                    "memory": memory,
                    "architecture": architecture,
                    "storage": storage,
                    "interfaces": interfaces,
                }
                pods = Pod.objects.get_pods(
                    request.user, PodPermission.dynamic_compose
                )
                if zone is not None:
                    pods = pods.filter(zone__name=zone)
                if pods:
                    (
                        machine,
                        storage,
                        interfaces,
                    ) = get_allocated_composed_machine(
                        request,
                        data,
                        storage,
                        interfaces,
                        pods,
                        form,
                        input_constraints,
                    )

            if machine is None:
                constraints = form.describe_constraints()
                if constraints == "":
                    # No constraints. That means no machines at all were
                    # available.
                    message = "No machine available."
                elif system_id is not None:
                    message = (
                        f"No machine with system ID {system_id} available."
                    )
                else:
                    message = (
                        "No available machine matches constraints: %s "
                        '(resolved to "%s")'
                        % (str(input_constraints), constraints)
                    )
                raise NodesNotAvailable(message)
            if not dry_run:
                machine.acquire(
                    request.user,
                    agent_name=options.agent_name,
                    comment=options.comment,
                    bridge_all=options.bridge_all,
                    bridge_type=options.bridge_type,
                    bridge_stp=options.bridge_stp,
                    bridge_fd=options.bridge_fd,
                )
            machine.constraint_map = storage.get(machine.id, {})
            machine.constraints_by_type = {}
            # Need to get the interface constraints map into the proper format
            # to return it here.
            # Backward compatibility: provide the storage constraints in both
            # formats.
            if len(machine.constraint_map) > 0:
                machine.constraints_by_type["storage"] = {}
                new_storage = machine.constraints_by_type["storage"]
                # Convert this to the "new style" constraints map format.
                for storage_key in machine.constraint_map:
                    # Each key in the storage map is actually a value which
                    # contains the ID of the matching storage device.
                    # Convert this to a label: list-of-matches format, to
                    # match how the constraints will be done going forward.
                    new_key = machine.constraint_map[storage_key]
                    matches = new_storage.get(new_key, [])
                    matches.append(storage_key)
                    new_storage[new_key] = matches
            if len(interfaces) > 0:
                machine.constraints_by_type["interfaces"] = {
                    label: interfaces.get(label, {}).get(machine.id)
                    for label in interfaces
                }
            if verbose:
                machine.constraints_by_type["verbose_storage"] = storage
                machine.constraints_by_type["verbose_interfaces"] = interfaces
            return machine

    def _get_chassis_param(self, request):
        power_type_names = [
            pt["name"] for pt in get_all_power_types() if pt["can_probe"]
        ]

        # NOTE: The http API accepts two additional names for backwards
        # compatability. Previously the hardcoded list of chassis_type's was
        # stored here and included powerkvm and seamicro15k. Neither of these
        # are valid power driver names but they can be treated as virsh and
        # sm15k.
        power_type_names.extend(["powerkvm", "seamicro15k"])

        chassis_type = get_mandatory_param(
            request.POST,
            "chassis_type",
            validator=validators.OneOf(power_type_names),
        )

        # Convert sm15k to seamicro15k. This code was written to work with
        # 'seamicro15k' but the power driver name in the provisioningserver is
        # 'sm15k'. The following code expects the longer name. See the NOTE
        # above for more context. Both powerkvm and virsh were previously
        # supported so they don't need to be converted.
        if chassis_type == "sm15k":
            chassis_type = "seamicro15k"

        return chassis_type

    @admin_method
    @operation(idempotent=False)
    def add_chassis(self, request):
        """@description-title Add special hardware
        @description Add special hardware types.

        @param (string) "chassis_type" [required=true,formatting=true] The type
        of hardware:

        - ``hmcz``: IBM Hardware Management Console (HMC) for Z
        - ``mscm``: Moonshot Chassis Manager.
        - ``msftocs``: Microsoft OCS Chassis Manager.
        - ``powerkvm``: Virtual Machines on Power KVM, managed by Virsh.
        - ``proxmox``: Virtual Machines managed by Proxmox
        - ``recs_box``: Christmann RECS|Box servers.
        - ``sm15k``: Seamicro 1500 Chassis.
        - ``ucsm``: Cisco UCS Manager.
        - ``virsh``: virtual machines managed by Virsh.
        - ``vmware`` is the type for virtual machines managed by VMware.

        @param (string) "hostname" [required=true] The URL, hostname, or IP
        address to access the chassis.

        @param (string) "username" [required=false] The username used to access
        the chassis. This field is required for the recs_box, seamicro15k,
        vmware, mscm, msftocs, ucsm, and hmcz chassis types.

        @param (string) "password" [required=false] The password used to access
        the chassis. This field is required for the ``recs_box``,
        ``seamicro15k``, ``vmware``, ``mscm``, ``msftocs``, ``ucsm``, and
        ``hmcz`` chassis types.

        @param (string) "accept_all" [required=false] If true, all enlisted
        machines will be commissioned.

        @param (string) "rack_controller" [required=false] The system_id of the
        rack controller to send the add chassis command through. If none is
        specifed MAAS will automatically determine the rack controller to use.

        @param (string) "domain" [required=false] The domain that each new
        machine added should use.

        @param (string) "prefix_filter" [required=false] (``virsh``,
        ``vmware``, ``powerkvm``, ``proxmox``, ``hmcz`` only.) Filter machines
        with supplied prefix.

        @param (string) "power_control" [required=false] (``seamicro15k`` only)
        The power_control to use, either ipmi (default), restapi, or restapi2.

        The following are optional if you are adding a proxmox chassis.

        @param (string) "token_name" [required=false] The name the
        authentication token to be used instead of a password.

        @param (string) "token_secret" [required=false] The token secret
        to be used in combination with the power_token_name used in place of
        a password.

        @param (boolean) "verify_ssl" [required=false] Whether SSL
        connections should be verified.

        The following are optional if you are adding a recs_box, vmware or
        msftocs chassis.

        @param (int) "port" [required=false] (``recs_box``, ``vmware``,
        ``msftocs`` only) The port to use when accessing the chassis.

        The following are optional if you are adding a vmware chassis:

        @param (string) "protocol" [required=false] (``vmware`` only) The
        protocol to use when accessing the VMware chassis (default: https).

        :return: A string containing the chassis powered on by which rack
            controller.

        @success (http-status-code) "200" 200
        @success (content) "success-content"
            Asking maas-run to add machines from chassis

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to
        access the rack controller.

        @error (http-status-code) "404" 404
        @error (content) "not-found" No rack controller can be found that has
        access to the given URL.
        @error-example "not-found"
            Not Found

        @error (http-status-code) "400" 400
        @error (content) "bad-params" Required parameters are missing.
        """

        chassis_type = self._get_chassis_param(request)

        hostname = get_mandatory_param(request.POST, "hostname")

        if chassis_type in (
            "hmcz",
            "mscm",
            "msftocs",
            "recs_box",
            "seamicro15k",
            "ucsm",
            "vmware",
        ):
            username = get_mandatory_param(request.POST, "username")
            password = get_mandatory_param(request.POST, "password")
            token_name = None
            token_secret = None
        elif chassis_type == "proxmox":
            username = get_mandatory_param(request.POST, "username")
            password = get_optional_param(request.POST, "password")
            token_name = get_optional_param(request.POST, "token_name")
            token_secret = get_optional_param(request.POST, "token_secret")
            if not any([password, token_name, token_secret]):
                return HttpResponseBadRequest(
                    "You must use a password or token with Proxmox."
                )
            elif all([password, token_name, token_secret]):
                return HttpResponseBadRequest(
                    "You may only use a password or token with Proxmox, "
                    "not both."
                )
            elif password is None and not all([token_name, token_secret]):
                return HttpResponseBadRequest(
                    "Proxmox requires both a token_name and token_secret."
                )
        else:
            username = get_optional_param(request.POST, "username")
            password = get_optional_param(request.POST, "password")
            token_name = None
            token_secret = None
            if username is not None and chassis_type in ("powerkvm", "virsh"):
                return HttpResponseBadRequest(
                    "username can not be specified when using the %s chassis."
                    % chassis_type,
                    content_type=(
                        "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                    ),
                )

        accept_all = get_optional_param(request.POST, "accept_all")
        if isinstance(accept_all, str):
            accept_all = accept_all.lower() == "true"
        else:
            accept_all = False

        # Only available with virsh, vmware, powerkvm, and proxmox
        prefix_filter = get_optional_param(request.POST, "prefix_filter")
        if prefix_filter is not None and chassis_type not in (
            "hmcz",
            "powerkvm",
            "virsh",
            "vmware",
            "proxmox",
        ):
            return HttpResponseBadRequest(
                "prefix_filter is unavailable with the %s chassis type"
                % chassis_type,
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
            )

        # Only available with seamicro15k
        power_control = get_optional_param(
            request.POST,
            "power_control",
            validator=validators.OneOf(["ipmi", "restapi", "restapi2"]),
        )
        if power_control is not None and chassis_type != "seamicro15k":
            return HttpResponseBadRequest(
                "power_control is unavailable with the %s chassis type"
                % chassis_type,
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
            )

        # Only available with vmware, recs_box or msftocs
        port = get_optional_param(
            request.POST, "port", validator=validators.Int(min=1, max=65535)
        )
        if port is not None and chassis_type not in (
            "msftocs",
            "recs_box",
            "vmware",
        ):
            return HttpResponseBadRequest(
                "port is unavailable with the %s chassis type" % chassis_type,
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
            )

        # Only available with vmware
        protocol = get_optional_param(request.POST, "protocol")
        if protocol is not None and chassis_type != "vmware":
            return HttpResponseBadRequest(
                "protocol is unavailable with the %s chassis type"
                % chassis_type,
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
            )

        verify_ssl = get_optional_param(
            request.POST, "verify_ssl", default=False, validator=StringBool
        )

        # If given a domain make sure it exists first
        domain_name = get_optional_param(request.POST, "domain")
        if domain_name is not None:
            try:
                domain = Domain.objects.get(id=int(domain_name))
            except ValueError:
                try:
                    domain = Domain.objects.get(name=domain_name)
                except Domain.DoesNotExist:
                    return HttpResponseNotFound(
                        "Unable to find specified domain %s" % domain_name
                    )
            domain_name = domain.name

        rack_controller = get_optional_param(request.POST, "rack_controller")
        if rack_controller is None:
            rack = RackController.objects.get_accessible_by_url(hostname)
            if rack:
                racks = [rack]
            else:
                racks = RackController.objects.all()
        else:
            try:
                racks = [
                    RackController.objects.get(
                        Q(system_id=rack_controller)
                        | Q(hostname=rack_controller)
                    )
                ]
            except RackController.DoesNotExist:
                return HttpResponseNotFound(
                    "Unable to find specified rack %s" % rack_controller,
                    content_type=(
                        "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                    ),
                )

        # Ask all racks to add the chassis. add_chassis() is kind of
        # idempotent, so nodes won't be added multiple times by
        # different racks.
        for rack in racks:
            # Ideally we should break after the first rack managed to
            # add the chassis. But currently add_chassis() doesn't
            # return whether it succeeds.
            rack.add_chassis(
                request.user.username,
                chassis_type,
                hostname,
                username,
                password,
                accept_all,
                domain_name,
                prefix_filter,
                power_control,
                port,
                protocol,
                token_name,
                token_secret,
                verify_ssl,
            )

        return HttpResponse(
            "Asking %s to add machines from chassis %s"
            % (", ".join(rack.hostname for rack in racks), hostname),
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET),
        )

    @operation(idempotent=False)
    def clone(self, request):
        """@description-title Clone storage and/or interface configurations
        @description Clone storage and/or interface configurations

        A machine storage and/or interface configuration can be cloned to a
        set of destination machines.

        For storage configuration, cloning the destination machine must have at
        least the same number of physical block devices or more, along with
        the physical block devices being the same size or greater.

        For interface configuration, cloning the destination machine must have
        at least the same number of interfaces with the same names. The
        destination machine can have more interfaces than the source, as long
        as the subset of interfaces on the destination have the same matching
        names as the source.

        @param (string) "source" [required=true] The system_id of the machine
        that is the source of the configuration.

        @param (string) "destinations" [required=true] A list of system_ids to
        clone the configuration to.

        @param (boolean) "interfaces" [required=True] Whether to clone
        interface configuration. Defaults to False.

        @param (boolean) "storage" [required=True] Whether to clone storage
        configuration. Defaults to False.

        @success (http-status-code) "204" 204

        @error (http-status-code) "400" 400
        @error (content) "not-found" Source and/or destinations are not found.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user not authenticated.
        """
        form = CloneForm(request.user, data=request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()
        # 204 HTTP No Content (not actually DELETED).
        return rc.DELETED

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("machines_handler", [])
