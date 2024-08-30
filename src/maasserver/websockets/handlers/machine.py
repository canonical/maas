# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The machine handler for the WebSocket connection."""

from collections import defaultdict
from functools import partial
import logging
from operator import itemgetter

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
    TextField,
    Value,
    When,
)
from django.db.models.functions import Concat

from maasserver.enum import (
    BMC_TYPE,
    INTERFACE_LINK_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUSES_MAP,
)
from maasserver.exceptions import NodeActionError, NodeStateViolation
from maasserver.forms import (
    AddPartitionForm,
    AdminMachineForm,
    AdminMachineWithMACAddressesForm,
    CreateBcacheForm,
    CreateCacheSetForm,
    CreateLogicalVolumeForm,
    CreateRaidForm,
    CreateVMFSForm,
    CreateVolumeGroupForm,
    FormatBlockDeviceForm,
    FormatPartitionForm,
    UpdatePhysicalBlockDeviceForm,
    UpdateVirtualBlockDeviceForm,
    UpdateVMFSForm,
)
from maasserver.forms.filesystem import (
    MountFilesystemForm,
    MountNonStorageFilesystemForm,
    UnmountNonStorageFilesystemForm,
)
from maasserver.forms.interface import (
    AcquiredBridgeInterfaceForm,
    BondInterfaceForm,
    BridgeInterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.forms.interface_link import InterfaceLinkForm
from maasserver.models import (
    BlockDevice,
    CacheSet,
    Event,
    Filesystem,
    Interface,
    Machine,
    Node,
    OwnerData,
    Partition,
    Subnet,
    VolumeGroup,
)
from maasserver.node_action import compile_node_actions, get_node_action
from maasserver.permissions import NodePermission
from maasserver.storage_layouts import (
    StorageLayoutError,
    StorageLayoutForm,
    StorageLayoutMissingBootDiskError,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    dehydrate_certificate,
    HandlerDoesNotExistError,
    HandlerError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.node import node_prefetch, NodeHandler
from metadataserver.enum import HARDWARE_TYPE, RESULT_TYPE
from provisioningserver.certificates import Certificate
from provisioningserver.enum import POWER_STATE
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.exceptions import UnknownPowerType
from provisioningserver.utils.twisted import asynchronous

log = LegacyLogger()


def _build_simple_status_q():
    return Case(
        *[
            When(status__in=values, then=Value(status))
            for status, values in SIMPLIFIED_NODE_STATUSES_MAP.items()
        ],
        default=Value(SIMPLIFIED_NODE_STATUS.OTHER),
    )


class MachineHandler(NodeHandler):
    class Meta(NodeHandler.Meta):
        abstract = False
        form_requires_request = True
        queryset = (
            node_prefetch(Machine.objects.all())
            .prefetch_related(
                "current_config__blockdevice_set__physicalblockdevice__"
                "partitiontable_set__partitions__filesystem_set"
            )
            .prefetch_related(
                "current_config__blockdevice_set__virtualblockdevice__"
                "partitiontable_set__partitions"
            )
        )
        node_total_storage_query_set = (
            Machine.objects.select_related("current_config")
            .annotate(
                storage=Sum(
                    "current_config__blockdevice__physicalblockdevice__size"
                )
            )
            .filter(pk=OuterRef("pk"))
        )
        list_queryset = (
            Machine.objects.all()
            .select_related("owner", "zone", "domain", "bmc", "current_config")
            .prefetch_related(
                "current_config__blockdevice_set__physicalblockdevice__"
                "partitiontable_set__partitions"
            )
            .prefetch_related(
                "current_config__blockdevice_set__physicalblockdevice__numa_node"
            )
            .prefetch_related(
                "current_config__blockdevice_set__virtualblockdevice__"
                "partitiontable_set__partitions"
            )
            .prefetch_related(
                "current_config__interface_set__ip_addresses__subnet__vlan__space"
            )
            .prefetch_related(
                "current_config__interface_set__ip_addresses__subnet__vlan__fabric"
            )
            .prefetch_related("current_config__interface_set__numa_node")
            .prefetch_related("current_config__interface_set__vlan__space")
            .prefetch_related("current_config__interface_set__vlan__fabric")
            .prefetch_related("boot_interface__vlan__space")
            .prefetch_related("boot_interface__vlan__fabric")
            .prefetch_related("tags")
            .prefetch_related("pool")
            .prefetch_related("ownerdata_set")
            .annotate(
                status_message_text=Subquery(
                    Event.objects.filter(
                        node=OuterRef("pk"), type__level__gte=logging.INFO
                    )
                    .order_by("-created", "-id")
                    .annotate(
                        message=Concat(
                            F("type__description"),
                            Value(" - "),
                            F("description"),
                            output_field=TextField(),
                        ),
                    )
                    .values("message")[:1]
                ),
                physical_disk_count=Count(
                    "current_config__blockdevice__physicalblockdevice",
                    distinct=True,
                ),
                total_storage=Subquery(
                    node_total_storage_query_set.values("storage"),
                    output_field=IntegerField(),
                ),
                pxe_mac=F("boot_interface__mac_address"),
                fabric_name=F("boot_interface__vlan__fabric__name"),
                node_fqdn=Concat(
                    "hostname",
                    Value("."),
                    "domain__name",
                    output_field=CharField(),
                ),
                simple_status=_build_simple_status_q(),
            )
        )

        use_sqlalchemy_list = (
            Machine.objects.all()
            .select_related("owner", "zone", "domain", "bmc", "current_config")
            .prefetch_related("pool")
            .prefetch_related("current_config__interface_set")
            .annotate(
                physical_disk_count=Count(
                    "current_config__blockdevice__physicalblockdevice",
                    distinct=True,
                ),
                total_storage=Subquery(
                    node_total_storage_query_set.values("storage"),
                    output_field=IntegerField(),
                ),
                pxe_mac=F("boot_interface__mac_address"),
                fabric_name=F("boot_interface__vlan__fabric__name"),
                node_fqdn=Concat(
                    "hostname",
                    Value("."),
                    "domain__name",
                    output_field=CharField(),
                ),
                simple_status=_build_simple_status_q(),
            )
        )
        allowed_methods = [
            "list",
            "list_ids",
            "get",
            "create",
            "update",
            "action",
            "set_active",
            "unsubscribe",
            "check_power",
            "create_physical",
            "create_vlan",
            "create_bond",
            "create_bridge",
            "update_interface",
            "delete_interface",
            "link_subnet",
            "unlink_subnet",
            "mount_special",
            "unmount_special",
            "update_filesystem",
            "update_disk",
            "delete_disk",
            "delete_partition",
            "delete_volume_group",
            "delete_cache_set",
            "delete_filesystem",
            "delete_vmfs_datastore",
            "update_vmfs_datastore",
            "create_partition",
            "create_cache_set",
            "create_bcache",
            "create_raid",
            "create_volume_group",
            "create_logical_volume",
            "create_vmfs_datastore",
            "set_boot_disk",
            "apply_storage_layout",
            "default_user",
            "get_summary_xml",
            "get_summary_yaml",
            "set_script_result_suppressed",
            "set_script_result_unsuppressed",
            "get_latest_failed_testing_script_results",
            "get_workload_annotations",
            "set_workload_annotations",
            "filter_groups",
            "filter_options",
            "count",
        ]
        form = AdminMachineWithMACAddressesForm
        exclude = [
            "dynamic",
            "status_expires",
            "previous_status",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_queried",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
            "instance_power_parameters",
            "address_ttl",
            "url",
            "dns_process",
            "managing_process",
            "last_image_sync",
            "install_rackd",
            "install_kvm",
            "register_vmhost",
            "current_config",
        ]
        list_fields = [
            "id",
            "system_id",
            "hostname",
            "parent",
            "locked",
            "owner",
            "cpu_count",
            "description",
            "error_description",
            "memory",
            "power_state",
            "domain",
            "pool",
            "zone",
        ]
        list_exclude = [
            "commissioning_start_time",
            "commissioning_status",
        ] + exclude
        listen_channels = ["machine"]
        create_permission = NodePermission.admin
        view_permission = NodePermission.view
        edit_permission = NodePermission.admin
        delete_permission = NodePermission.admin
        use_paginated_list = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._deployed = False

    def _full_dehydrate_for_listing(self, machine, for_list=True):
        obj = {
            "id": machine.id,
            "actions": list(compile_node_actions(machine, self.user).keys()),
        }

        self._add_permissions(machine, obj)
        return obj

    def list_ids(self, params):
        return super().list(
            params,
            use_sqlalchemy_list=True,
            full_dehydrate_function=self._full_dehydrate_for_listing,
        )

    def _list_sqlalchemy(self, params):
        res = self.list_ids(params)
        return self.api_client.post("machines", json=res).json()

    def list(self, params):
        res = self._list_sqlalchemy(params)
        return res

    def get_queryset(
        self,
        use_sqlalchemy_list=False,
        for_list=False,
        perm=NodePermission.view,
    ):
        """Return `QuerySet` for devices only viewable by `user`."""
        return Machine.objects.get_nodes(
            self.user,
            perm,
            from_nodes=super().get_queryset(
                use_sqlalchemy_list=use_sqlalchemy_list, for_list=for_list
            ),
        )

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data = super().dehydrate(obj, data, for_list=for_list)
        data["parent"] = getattr(obj.parent, "system_id", None)
        # Try to use the annotated value from the queryset. Otherwise fallback
        # to the method on the machine.
        if hasattr(obj, "status_message_text"):
            data["status_message"] = obj.status_message_text
        else:
            data["status_message"] = obj.status_message()

        if obj.is_machine or not for_list:
            data["pxe_mac"] = ""
            data["vlan"] = None
            data["ip_addresses"] = None
            if getattr(obj, "pxe_mac", None):
                data["pxe_mac"] = str(obj.pxe_mac)
                data["vlan"] = self.dehydrate_vlan(obj, obj.boot_interface)
            else:
                boot_interface = obj.get_boot_interface()
                if boot_interface is not None:
                    data["pxe_mac"] = "%s" % boot_interface.mac_address
                    data["vlan"] = self.dehydrate_vlan(obj, boot_interface)
            if data["pxe_mac"] != "":
                data["ip_addresses"] = self.dehydrate_all_ip_addresses(obj)

        # Needed for machines to show up in the Pod details page.
        data["pod"] = None
        if obj.bmc is not None and obj.bmc.bmc_type == BMC_TYPE.POD:
            data["pod"] = self.dehydrate_pod(obj.bmc)

        if not for_list:
            cpu_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.CPU, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["cpu_test_status"] = self.dehydrate_test_statuses(
                cpu_script_results
            )

            memory_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.MEMORY, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["memory_test_status"] = self.dehydrate_test_statuses(
                memory_script_results
            )

            network_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.NETWORK, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["network_test_status"] = self.dehydrate_test_statuses(
                network_script_results
            )

            storage_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.STORAGE, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["storage_test_status"] = self.dehydrate_test_statuses(
                storage_script_results
            )
        else:
            data["cpu_test_status"] = self.dehydrate_test_statuses_for_list(
                self._script_results_for_list.get(obj.id, {}).get(
                    HARDWARE_TYPE.CPU, None
                )
            )
            data["memory_test_status"] = self.dehydrate_test_statuses_for_list(
                self._script_results_for_list.get(obj.id, {}).get(
                    HARDWARE_TYPE.MEMORY, None
                )
            )
            data["network_test_status"] = (
                self.dehydrate_test_statuses_for_list(
                    self._script_results_for_list.get(obj.id, {}).get(
                        HARDWARE_TYPE.NETWORK, None
                    )
                )
            )
            data["storage_test_status"] = (
                self.dehydrate_test_statuses_for_list(
                    self._script_results_for_list.get(obj.id, {}).get(
                        HARDWARE_TYPE.STORAGE
                    )
                )
            )

        if not for_list:
            # Add info specific to a machine.
            data["workload_annotations"] = OwnerData.objects.get_owner_data(
                obj
            )
            data["show_os_info"] = self.dehydrate_show_os_info(obj)
            devices = [
                self.dehydrate_device(device) for device in obj.children.all()
            ]
            data["devices"] = sorted(devices, key=itemgetter("fqdn"))

            interface_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.NETWORK, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["interface_test_status"] = self.dehydrate_test_statuses(
                interface_script_results
            )
            node_script_results = [
                script_result
                for script_result in self._script_results.get(obj.id, {}).get(
                    HARDWARE_TYPE.NODE, []
                )
                if script_result.script_set.result_type == RESULT_TYPE.TESTING
            ]
            data["other_test_status"] = self.dehydrate_test_statuses(
                node_script_results
            )

            # include certificate info if present
            certificate = obj.get_power_parameters().get("certificate")
            key = obj.get_power_parameters().get("key")
            if certificate and key:
                cert = Certificate.from_pem(certificate, key)
                data["certificate"] = dehydrate_certificate(cert)

        return data

    def dehydrate_show_os_info(self, obj):
        """Return True if OS information should show in the UI."""
        return (
            obj.status == NODE_STATUS.DEPLOYING
            or obj.status == NODE_STATUS.FAILED_DEPLOYMENT
            or obj.status == NODE_STATUS.DEPLOYED
            or obj.status == NODE_STATUS.RELEASING
            or obj.status == NODE_STATUS.FAILED_RELEASING
            or obj.status == NODE_STATUS.DISK_ERASING
            or obj.status == NODE_STATUS.FAILED_DISK_ERASING
        )

    def dehydrate_device(self, device):
        """Return the `Device` formatted for JSON encoding."""
        return {
            "fqdn": device.fqdn,
            "interfaces": [
                self.dehydrate_interface(interface, device)
                for interface in device.current_config.interface_set.all()
            ],
        }

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action == "create" and self._deployed:
            return AdminMachineForm
        if action in ("create", "update"):
            return AdminMachineWithMACAddressesForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form."""
        all_macs = list(params.get("extra_macs", []))
        if "pxe_mac" in params:
            all_macs.insert(0, params["pxe_mac"])

        new_params = self.preprocess_node_form(action, params)
        # Only copy the allowed fields into `new_params` to be passed into
        # the form.
        new_params["mac_addresses"] = all_macs
        new_params["hostname"] = params.get("hostname")
        new_params["architecture"] = params.get("architecture")
        new_params["power_type"] = params.get("power_type")
        new_params["power_parameters"] = params.get("power_parameters")
        new_params["deployed"] = params.get("deployed")
        if params.get("pool"):
            new_params["pool"] = params["pool"]["name"]
        if "min_hwe_kernel" in params:
            new_params["min_hwe_kernel"] = params["min_hwe_kernel"]

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }

        return super().preprocess_form(action, new_params)

    def create(self, params):
        self._deployed = bool(params.get("deployed", False))
        data = super().create(params)
        if not self._deployed:
            machine = Node.objects.get(system_id=data["system_id"])
            # Start the commissioning process right away, which has the
            # desired side effect of initializing the node's power state.
            d = machine.start_commissioning(self.user)
            # Silently ignore errors to prevent tracebacks. The commissioning
            # callbacks have their own logging. This fixes LP1600328.
            d.addErrback(lambda _: None)

        return data

    def mount_special(self, params):
        """Mount a special-purpose filesystem, like tmpfs.

        :param fstype: The filesystem type. This must be a filesystem that
            does not require a block special device.
        :param mount_point: Path on the filesystem to mount.
        :param mount_option: Options to pass to mount(8).

        :attention: This is more or less a copy of `mount_special` from
            `m.api.machines`.
        """
        machine = self._get_node_or_permission_error(
            params, permission=NodePermission.edit
        )
        if machine.locked:
            raise HandlerPermissionError()
        self._preflight_special_filesystem_modifications("mount", machine)
        form = MountNonStorageFilesystemForm(machine, data=params)
        if form.is_valid():
            form.save()
        else:
            raise HandlerValidationError(form.errors)

    def unmount_special(self, params):
        """Unmount a special-purpose filesystem, like tmpfs.

        :param mount_point: Path on the filesystem to unmount.

        :attention: This is more or less a copy of `unmount_special` from
            `m.api.machines`.
        """
        machine = self._get_node_or_permission_error(
            params, permission=NodePermission.edit
        )
        if machine.locked:
            raise HandlerPermissionError()
        self._preflight_special_filesystem_modifications("unmount", machine)
        form = UnmountNonStorageFilesystemForm(machine, data=params)
        if form.is_valid():
            form.save()
        else:
            raise HandlerValidationError(form.errors)

    def _preflight_special_filesystem_modifications(self, op, machine):
        """Check that `machine` is okay for special fs modifications."""
        if self.user.has_perm(NodePermission.admin, machine):
            statuses_permitted = {NODE_STATUS.READY, NODE_STATUS.ALLOCATED}
        else:
            statuses_permitted = {NODE_STATUS.ALLOCATED}
        if machine.status not in statuses_permitted:
            status_names = sorted(
                title
                for value, title in NODE_STATUS_CHOICES
                if value in statuses_permitted
            )
            raise NodeStateViolation(
                "Cannot %s the filesystem because the machine is not %s."
                % (op, " or ".join(status_names))
            )

    def listen(self, channel, action, pk):
        """Called when the handler listens for events on channels with
        `Meta.listen_channels`.

        :param channel: Channel event occured on.
        :param action: Action that caused this event.
        :param pk: Id of the object.
        """
        # if loaded / not unsubscrived, allow listen events
        if pk in self.cache["loaded_pks"] or pk == self.cache.get("active_pk"):
            return self.get_object({self._meta.pk: pk})

    def update_filesystem(self, params):
        node = self._get_node_or_permission_error(
            params, permission=NodePermission.edit
        )
        if node.locked:
            raise HandlerPermissionError()
        block_id = params.get("block_id")
        partition_id = params.get("partition_id")
        fstype = params.get("fstype")
        mount_point = params.get("mount_point")
        mount_options = params.get("mount_options")

        if node.status not in [NODE_STATUS.ALLOCATED, NODE_STATUS.READY]:
            raise HandlerError(
                "Node must be allocated or ready to edit storage"
            )

        # If this is on a block device, check if the tags need to be updated.
        # (The client sends them in from the same form.)
        blockdevice = None
        if block_id is not None:
            blockdevice = BlockDevice.objects.get(
                id=block_id, node_config=node.current_config
            )
            tags = params.get("tags", None)
            # If the tags parameter was left out, that means "don't touch the
            # tags". (An empty list means "clear the tags".)
            if tags is not None:
                tags = [tag["text"] for tag in tags]
                if set(blockdevice.tags) != set(tags):
                    blockdevice.tags = tags
                    blockdevice.save()
        if partition_id:
            self.update_partition_filesystem(
                node.current_config,
                partition_id,
                fstype,
                mount_point,
                mount_options,
            )
        elif blockdevice is not None:
            self.update_blockdevice_filesystem(
                blockdevice, fstype, mount_point, mount_options
            )

    def update_partition_filesystem(
        self, node_config, partition_id, fstype, mount_point, mount_options
    ):
        partition = Partition.objects.get(
            id=partition_id,
            partition_table__block_device__node_config=node_config,
        )
        fs = partition.get_effective_filesystem()
        if not fstype:
            if fs:
                fs.delete()
                return
        if fs is None or fstype != fs.fstype:
            form = FormatPartitionForm(partition, {"fstype": fstype})
            if not form.is_valid():
                raise HandlerError(form.errors)
            form.save()
            fs = partition.get_effective_filesystem()
        if mount_point != fs.mount_point:
            # XXX: Elsewhere, a mount_point of "" would somtimes mean that the
            # filesystem is mounted, sometimes that it is *not* mounted. Which
            # is correct was not clear from the code history, so the existing
            # behaviour is maintained here.
            if mount_point is None or mount_point == "":
                fs.mount_point = None
                fs.mount_options = None
                fs.save()
            else:
                form = MountFilesystemForm(
                    partition.get_effective_filesystem(),
                    {
                        "mount_point": mount_point,
                        "mount_options": mount_options,
                    },
                )
                if not form.is_valid():
                    raise HandlerError(form.errors)
                else:
                    form.save()

    def update_blockdevice_filesystem(
        self, blockdevice, fstype, mount_point, mount_options
    ):
        fs = blockdevice.get_effective_filesystem()
        if not fstype:
            if fs:
                fs.delete()
            return
        if fs is None or fstype != fs.fstype:
            form = FormatBlockDeviceForm(blockdevice, {"fstype": fstype})
            if not form.is_valid():
                raise HandlerError(form.errors)
            form.save()
            fs = blockdevice.get_effective_filesystem()
        if mount_point != fs.mount_point:
            # XXX: Elsewhere, a mount_point of "" would somtimes mean that the
            # filesystem is mounted, sometimes that it is *not* mounted. Which
            # is correct was not clear from the code history, so the existing
            # behaviour is maintained here.
            if mount_point is None or mount_point == "":
                fs.mount_point = None
                fs.mount_options = None
                fs.save()
            else:
                form = MountFilesystemForm(
                    blockdevice.get_effective_filesystem(),
                    {
                        "mount_point": mount_point,
                        "mount_options": mount_options,
                    },
                )
                if not form.is_valid():
                    raise HandlerError(form.errors)
                else:
                    form.save()

    def update_disk(self, params):
        """Update disk information."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        device = BlockDevice.objects.get(
            id=params["block_id"], node_config=node.current_config
        ).actual_instance
        if device.type == "physical":
            form = UpdatePhysicalBlockDeviceForm(instance=device, data=params)
        elif device.type == "virtual":
            form = UpdateVirtualBlockDeviceForm(instance=device, data=params)
        else:
            raise HandlerError(
                "Cannot update block device of type %s" % device.type
            )
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            disk_obj = form.save()
            self._update_obj_tags(disk_obj, params)
            if "fstype" in params:
                self.update_blockdevice_filesystem(
                    disk_obj,
                    params["fstype"],
                    params.get("mount_point", ""),
                    params.get("mount_options", ""),
                )

    def delete_disk(self, params):
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        block_id = params.get("block_id")
        if block_id is not None:
            block_device = BlockDevice.objects.get(
                id=block_id, node_config=node.current_config
            )
            block_device.delete()

    def delete_partition(self, params):
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        node_config = node.current_config
        partition_id = params.get("partition_id")
        if partition_id is None:
            return

        partition = Partition.objects.get(
            id=partition_id,
            partition_table__block_device__node_config=node_config,
        )
        partition.partition_table.delete_partition(partition)

    def delete_volume_group(self, params):
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        volume_group_id = params.get("volume_group_id")
        if volume_group_id is not None:
            volume_group = VolumeGroup.objects.get(id=volume_group_id)
            if volume_group.get_node() != node:
                raise VolumeGroup.DoesNotExist()
            volume_group.delete()

    def delete_cache_set(self, params):
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        cache_set_id = params.get("cache_set_id")
        if cache_set_id is not None:
            cache_set = CacheSet.objects.get(id=cache_set_id)
            if cache_set.get_node() != node:
                raise CacheSet.DoesNotExist()
            cache_set.delete()

    def delete_filesystem(self, params):
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        blockdevice_id = params.get("blockdevice_id")
        partition_id = params.get("partition_id")
        filesystem_id = params.get("filesystem_id")
        if partition_id is None:
            blockdevice = BlockDevice.objects.get(
                node_config=node.current_config, id=blockdevice_id
            )
            fs = Filesystem.objects.get(
                block_device=blockdevice, id=filesystem_id
            )
        else:
            partition = Partition.objects.get(id=partition_id)
            fs = Filesystem.objects.get(partition=partition, id=filesystem_id)
        fs.delete()

    def _get_vmfs_datastore(self, params):
        """Get the VMFS datastore from the given system_id and id."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        vmfs_datastore_id = params.get("vmfs_datastore_id")
        try:
            vbd = node.virtualblockdevice_set.get(id=vmfs_datastore_id)
        except ObjectDoesNotExist:
            raise HandlerDoesNotExistError(
                f"VMFS datastore ({vmfs_datastore_id}) does not exist"
            )
        if not vbd.filesystem_group:
            raise HandlerDoesNotExistError(
                f"VMFS datastore ({vmfs_datastore_id}) does not exist"
            )
        return vbd.filesystem_group

    def delete_vmfs_datastore(self, params):
        """Delete a VMFS datastore."""
        vmfs = self._get_vmfs_datastore(params)
        vmfs.delete()

    def update_vmfs_datastore(self, params):
        """Add or remove block devices or partitions from a datastore."""
        vmfs = self._get_vmfs_datastore(params)
        form = UpdateVMFSForm(vmfs, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def create_partition(self, params):
        """Create a partition."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        disk_obj = BlockDevice.objects.get(
            id=params["block_id"], node_config=node.current_config
        )
        form = AddPartitionForm(disk_obj, {"size": params["partition_size"]})
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            partition = form.save()

        self._update_obj_tags(partition, params)
        if "fstype" in params:
            self.update_partition_filesystem(
                node.current_config,
                partition.id,
                params.get("fstype"),
                params.get("mount_point"),
                params.get("mount_options"),
            )

    def create_cache_set(self, params):
        """Create a cache set."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        block_id = params.get("block_id")
        partition_id = params.get("partition_id")

        data = {}
        if partition_id is not None:
            data["cache_partition"] = partition_id
        elif block_id is not None:
            data["cache_device"] = block_id
        else:
            raise HandlerError("Either block_id or partition_id is required.")

        form = CreateCacheSetForm(node=node, data=data)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def create_bcache(self, params):
        """Create a bcache."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        block_id = params.get("block_id")
        partition_id = params.get("partition_id")

        data = {
            "name": params["name"],
            "cache_set": params["cache_set"],
            "cache_mode": params["cache_mode"],
        }

        if partition_id is not None:
            data["backing_partition"] = partition_id
        elif block_id is not None:
            data["backing_device"] = block_id
        else:
            raise HandlerError("Either block_id or partition_id is required.")

        form = CreateBcacheForm(node=node, data=data)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            bcache = form.save()

        self._update_obj_tags(bcache.virtual_device, params)
        if "fstype" in params:
            self.update_blockdevice_filesystem(
                bcache.virtual_device,
                params.get("fstype"),
                params.get("mount_point"),
                params.get("mount_options"),
            )

    def create_raid(self, params):
        """Create a RAID."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = CreateRaidForm(node=node, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            raid = form.save()

        self._update_obj_tags(raid.virtual_device, params)
        if "fstype" in params:
            self.update_blockdevice_filesystem(
                raid.virtual_device,
                params.get("fstype"),
                params.get("mount_point"),
                params.get("mount_options"),
            )

    def create_volume_group(self, params):
        """Create a volume group."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = CreateVolumeGroupForm(node=node, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def create_logical_volume(self, params):
        """Create a logical volume."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        volume_group = VolumeGroup.objects.get(id=params["volume_group_id"])
        if volume_group.get_node() != node:
            raise VolumeGroup.DoesNotExist()
        form = CreateLogicalVolumeForm(
            volume_group, {"name": params["name"], "size": params["size"]}
        )
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            logical_volume = form.save()

        self._update_obj_tags(logical_volume, params)
        if "fstype" in params:
            self.update_blockdevice_filesystem(
                logical_volume,
                params.get("fstype"),
                params.get("mount_point"),
                params.get("mount_options"),
            )

    def create_vmfs_datastore(self, params):
        """Create a VMFS datastore."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = CreateVMFSForm(node, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        else:
            form.save()

    def set_boot_disk(self, params):
        """Set the disk as the boot disk."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        device = BlockDevice.objects.get(
            id=params["block_id"], node_config=node.current_config
        ).actual_instance
        if device.type != "physical":
            raise HandlerError(
                "Only a physical disk can be set as the boot disk."
            )
        node.boot_disk = device
        node.save()

    def apply_storage_layout(self, params):
        """Apply the specified storage layout."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = StorageLayoutForm(required=True, data=params)
        if not form.is_valid():
            raise HandlerError(form.errors)
        storage_layout = params.get("storage_layout")
        try:
            node.set_storage_layout(storage_layout)
        except StorageLayoutMissingBootDiskError:
            raise HandlerError(
                "Machine is missing a boot disk; no storage layout can be "
                "applied."
            )
        except StorageLayoutError as e:
            raise HandlerError(
                "Failed to configure storage layout '%s': %s"
                % (storage_layout, str(e))
            )

    def _action(self, obj, action_name, extra_params):
        action = get_node_action(
            obj, action_name, self.user, request=self.request
        )
        if action is None:
            raise NodeActionError(
                f"{action_name} action is not available for this node."
            )
        return action.execute(**extra_params)

    def _bulk_action(self, filter_params, action_name, extra_params):
        """Find nodes that match the filter, then apply the given action to them."""
        machines = self._filter(
            self.get_queryset(for_list=True), None, filter_params
        )
        success_count = 0
        failed_system_ids = []
        failure_details = defaultdict(list)
        for machine in machines:
            try:
                self._action(machine, action_name, extra_params)
            except NodeActionError as e:
                failed_system_ids.append(machine.system_id)
                failure_details[str(e)].append(machine.system_id)
                log.error(
                    f"Bulk action ({action_name}) for {machine.system_id} failed: {e}"
                )
            else:
                success_count += 1

        return success_count, failed_system_ids, failure_details

    def _bulk_clone(self, source, filter_params, extra_params):
        """Bulk clone - special case of bulk_action."""
        clone_action = get_node_action(
            source, "clone", self.user, request=self.request
        )
        destinations = self._filter(
            self.get_queryset(for_list=True), None, filter_params
        )
        destination_ids = [node.system_id for node in destinations]
        return clone_action.execute(
            destinations=destination_ids, **extra_params
        )

    def action(self, params):
        """Perform the action on the object."""
        action_name = params.get("action")
        extra_params = params.get("extra", {})
        if action_name == "clone" and "filter" in params:
            return self._bulk_clone(
                self.get_object(params), params["filter"], extra_params
            )
        if "filter" in params:
            (
                success_count,
                failed_system_ids,
                failure_details,
            ) = self._bulk_action(params["filter"], action_name, extra_params)
            return {
                "success_count": success_count,
                "failed_system_ids": failed_system_ids,
                "failure_details": failure_details,
            }
        obj = self.get_object(params)
        return self._action(obj, action_name, extra_params)

    def _create_link_on_interface(self, interface, params):
        """Create a link on a new interface."""
        mode = params.get("mode", None)
        subnet_id = params.get("subnet", None)
        if mode is not None:
            if mode != INTERFACE_LINK_TYPE.LINK_UP:
                link_form = InterfaceLinkForm(instance=interface, data=params)
                if link_form.is_valid():
                    link_form.save()
                else:
                    raise ValidationError(link_form.errors)
            elif subnet_id is not None:
                link_ip = interface.ip_addresses.get(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip__isnull=True
                )
                link_ip.subnet = Subnet.objects.get(id=subnet_id)
                link_ip.save()

    def create_physical(self, params):
        """Create physical interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = PhysicalInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._update_obj_tags(interface, params)
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def create_vlan(self, params):
        """Create VLAN interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        params["parents"] = [params.pop("parent")]
        form = VLANInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._update_obj_tags(interface, params)
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def create_bond(self, params):
        """Create bond interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        form = BondInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._update_obj_tags(interface, params)
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def create_bridge(self, params):
        """Create bridge interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        if node.status == NODE_STATUS.ALLOCATED:
            form = AcquiredBridgeInterfaceForm(node=node, data=params)
        else:
            form = BridgeInterfaceForm(node=node, data=params)
        if form.is_valid():
            interface = form.save()
            self._update_obj_tags(interface, params)
            self._create_link_on_interface(interface, params)
        else:
            raise ValidationError(form.errors)

    def delete_interface(self, params):
        """Delete the interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        interface = Interface.objects.get(
            node_config__node=node, id=params["interface_id"]
        )
        interface.delete()

    @asynchronous(timeout=45)
    def check_power(self, params):
        """Check the power state of the node."""

        def eb_unknown(failure):
            failure.trap(UnknownPowerType, NotImplementedError)
            return POWER_STATE.UNKNOWN

        def eb_error(failure):
            log.err(failure, "Failed to update power state of machine.")
            return POWER_STATE.ERROR

        @transactional
        def update_state(state):
            if state in [POWER_STATE.ERROR, POWER_STATE.UNKNOWN]:
                # Update the power state only if it was an error or unknown as
                # that could have come from the previous errbacks.
                obj = self.get_object(params)
                obj.update_power_state(state)
            return state

        d = deferToDatabase(transactional(self.get_object), params)
        d.addCallback(lambda node: node.power_query())
        d.addErrback(eb_unknown)
        d.addErrback(eb_error)
        d.addCallback(partial(deferToDatabase, update_state))
        return d

    def get_workload_annotations(self, params):
        """Get the owner data for a machine, known as workload annotations."""
        machine = self._get_node_or_permission_error(
            params, permission=NodePermission.edit
        )
        return OwnerData.objects.get_owner_data(machine)

    def set_workload_annotations(self, params):
        """Set the owner data for a machine, known as workload annotations."""
        machine = self._get_node_or_permission_error(
            params, permission=NodePermission.edit
        )
        owner_data = {
            key: None if value == "" else value
            for key, value in params["workload_annotations"].items()
        }
        try:
            OwnerData.objects.set_owner_data(machine, owner_data)
        except ValueError as e:
            raise HandlerValidationError(str(e))
        return OwnerData.objects.get_owner_data(machine)

    def count(self, params):
        qs = self.get_queryset(for_list=True)
        if "filter" in params:
            qs = self._filter(qs, "list", params["filter"])
        return {"count": qs.count()}
