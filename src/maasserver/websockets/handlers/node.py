# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

from collections import Counter
from collections.abc import Iterable
from itertools import chain
import logging
from operator import attrgetter, itemgetter

from django.contrib.postgres.aggregates import ArrayAgg
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Subquery
from lxml import etree

from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    NODE_STATUS_SHORT_LABEL_CHOICES,
    NODE_TYPE,
    POWER_STATE,
    POWER_STATE_CHOICES,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUS_CHOICES_DICT,
    SIMPLIFIED_NODE_STATUS_LABEL_CHOICES,
    SIMPLIFIED_NODE_STATUSES_MAP_REVERSED,
)
from maasserver.forms import list_all_usable_architectures
from maasserver.forms.interface import (
    ControllerInterfaceForm,
    DeployedInterfaceForm,
    InterfaceForm,
)
from maasserver.models import (
    BlockDevice,
    BMC,
    CacheSet,
    Config,
    Domain,
    Event,
    Fabric,
    Interface,
    Node,
    NodeDevice,
    NUMANode,
    OwnerData,
    Partition,
    PhysicalBlockDevice,
    ResourcePool,
    ScriptResult,
    Space,
    StaticIPAddress,
    Subnet,
    Tag,
    User,
    VirtualBlockDevice,
    VLAN,
    VolumeGroup,
    Zone,
)
from maasserver.models.nodeprobeddetails import script_output_nsmap
from maasserver.models.scriptset import (
    get_status_from_list_qs,
    get_status_from_qs,
)
from maasserver.node_action import compile_node_actions
from maasserver.node_constraint_filter_forms import (
    FreeTextFilterNodeForm,
    get_field_argument_type,
    GROUPABLE_FIELDS,
    STATIC_FILTER_FIELDS,
)
from maasserver.permissions import NodePermission
from maasserver.storage_layouts import get_applied_storage_layout_for_node
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import human_readable_bytes, XMLToYAML
from maasserver.utils.osystems import make_hwe_kernel_ui_text
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerError,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.node_result import NodeResultHandler
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_FAILED,
)
from provisioningserver.refresh.node_info_scripts import (
    LIST_MODALIASES_OUTPUT_NAME,
)
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.utils.enum import map_enum_reverse

NODE_TYPE_TO_LINK_TYPE = {
    NODE_TYPE.DEVICE: "device",
    NODE_TYPE.MACHINE: "machine",
    NODE_TYPE.RACK_CONTROLLER: "controller",
    NODE_TYPE.REGION_CONTROLLER: "controller",
    NODE_TYPE.REGION_AND_RACK_CONTROLLER: "controller",
}


def node_prefetch(queryset):
    # this fetches two levels deep as get_node() gets called on the block
    # device associated to each partition
    blockdev_prefetch = (
        "current_config__blockdevice_set__partitiontable_set__partitions__"
        "partition_table__block_device__node_config__node__"
        "current_config__blockdevice_set"
    )
    return (
        queryset.all()
        .select_related(
            "owner", "zone", "pool", "domain", "bmc", "current_config"
        )
        .prefetch_related("current_config__blockdevice_set__filesystem_set")
        .prefetch_related(
            "current_config__blockdevice_set__physicalblockdevice__"
            "filesystem_set"
        )
        .prefetch_related(
            f"{blockdev_prefetch}__physicalblockdevice__partitiontable_set__partitions"
        )
        .prefetch_related(
            f"{blockdev_prefetch}__physicalblockdevice__numa_node"
        )
        .prefetch_related(f"{blockdev_prefetch}__virtualblockdevice")
        .prefetch_related(
            Prefetch(
                "current_config__interface_set",
                queryset=Interface.objects.order_by("name"),
            )
        )
        .prefetch_related(
            "current_config__interface_set__ip_addresses__subnet__vlan__space"
        )
        .prefetch_related(
            "current_config__interface_set__ip_addresses__subnet__vlan__fabric"
        )
        .prefetch_related("current_config__interface_set__numa_node")
        .prefetch_related("current_config__interface_set__vlan__fabric")
        .prefetch_related("boot_interface__vlan__fabric")
        .prefetch_related("nodemetadata_set")
        .prefetch_related("tags")
        .prefetch_related(
            Prefetch(
                "numanode_set", queryset=NUMANode.objects.order_by("index")
            )
        )
        .prefetch_related("numanode_set__hugepages_set")
    )


class NodeHandler(TimestampedModelHandler):
    class Meta:
        abstract = True
        pk = "system_id"
        bulk_pk = "system_ids"
        pk_type = str
        use_paginated_list = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._script_results = {}
        self._script_results_for_list = {}

    def update(self, params):
        data = super().update(params)
        if "tags" in params:
            instance = self.get_object(params)
            self._update_tags(instance, params["tags"])
            instance.save()
            return self.full_dehydrate(self.refetch(instance))
        return data

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_domain(self, domain):
        """Return domain name."""
        return {"id": domain.id, "name": domain.name}

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {"id": zone.id, "name": zone.name}

    def dehydrate_pool(self, pool):
        """Return pool name."""
        if pool is None:
            return None
        return {"id": pool.id, "name": pool.name}

    def dehydrate_pod(self, pod):
        return {"id": pod.id, "name": pod.name}

    def dehydrate_numanode(self, numa_node):
        details = {
            attr: getattr(numa_node, attr)
            for attr in ("id", "index", "memory", "cores")
        }
        details["hugepages_set"] = [
            self.dehydrate_hugepages(hugepages)
            for hugepages in numa_node.hugepages_set.all()
        ]
        return details

    def dehydrate_hugepages(self, hugepages):
        return {
            attr: getattr(hugepages, attr) for attr in ("page_size", "total")
        }

    def dehydrate_last_image_sync(self, last_image_sync):
        """Return formatted datetime."""
        return (
            dehydrate_datetime(last_image_sync)
            if last_image_sync is not None
            else None
        )

    def dehydrate_power_parameters(self, power_parameters):
        """Return power_parameters None if empty."""
        return None if power_parameters == "" else power_parameters

    def dehydrate_test_statuses(self, script_results):
        pending = 0
        running = 0
        passed = 0
        failed = 0
        for script_result in script_results:
            if script_result.status == SCRIPT_STATUS.PENDING:
                pending += 1
            elif script_result.status == SCRIPT_STATUS.RUNNING:
                running += 1
            elif script_result.status in (
                SCRIPT_STATUS.PASSED,
                SCRIPT_STATUS.SKIPPED,
            ):
                passed += 1
            elif script_result.status in (
                SCRIPT_STATUS.ABORTED,
                SCRIPT_STATUS.DEGRADED,
            ):
                # UI doesn't show aborted or degraded status in listing.
                continue
            else:
                failed += 1
        return {
            "status": get_status_from_qs(script_results),
            "pending": pending,
            "running": running,
            "passed": passed,
            "failed": failed,
        }

    def dehydrate_test_statuses_for_list(self, results: list[int]):
        return {
            "status": get_status_from_list_qs(results),
            # pending, running, passed and failed properties are not used by
            # the UI. Set them to a default value of -1 until the api contract
            # is reviewed
            "pending": -1,
            "running": -1,
            "passed": -1,
            "failed": -1,
        }

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["actions"] = list(compile_node_actions(obj, self.user).keys())
        data["link_type"] = NODE_TYPE_TO_LINK_TYPE[obj.node_type]
        data["tags"] = [tag.id for tag in obj.tags.all()]
        if obj.node_type == NODE_TYPE.MACHINE or (
            obj.is_controller and not for_list
        ):
            # Disk count and storage amount is shown on the machine listing
            # page and the machine and controllers details page.
            blockdevices = self.get_blockdevices_for(obj)
            if hasattr(obj, "physical_disk_count") and hasattr(
                obj, "total_storage"
            ):
                data["physical_disk_count"] = obj.physical_disk_count or 0
                data["storage"] = round(
                    (obj.total_storage or 0) / (1000**3),
                    1,
                )
            else:
                physical_blockdevices = [
                    blockdevice
                    for blockdevice in blockdevices
                    if isinstance(blockdevice, PhysicalBlockDevice)
                ]
                data["physical_disk_count"] = len(physical_blockdevices)
                data["storage"] = round(
                    sum(
                        blockdevice.size
                        for blockdevice in physical_blockdevices
                    )
                    / (1000**3),
                    1,
                )
            if not for_list:
                data["storage_tags"] = self.get_all_storage_tags(blockdevices)
                commissioning_script_results = []
                testing_script_results = []
                commissioning_start_time = None
                log_results = set()
                for hw_type in self._script_results.get(obj.id, {}).values():
                    for script_result in hw_type:
                        if script_result.status == SCRIPT_STATUS.ABORTED:
                            # LP: #1724235 - Ignore aborted scripts.
                            continue
                        elif (
                            script_result.script_set.result_type
                            == RESULT_TYPE.COMMISSIONING
                        ):
                            commissioning_script_results.append(script_result)
                            if commissioning_start_time is None or (
                                script_result.started is not None
                                and script_result.started
                                < commissioning_start_time
                            ):
                                commissioning_start_time = (
                                    script_result.started
                                )
                            if (
                                script_result.name in script_output_nsmap
                                and script_result.status
                                == SCRIPT_STATUS.PASSED
                            ):
                                log_results.add(script_result.name)
                        elif (
                            script_result.script_set.result_type
                            == RESULT_TYPE.TESTING
                        ):
                            testing_script_results.append(script_result)
                data["commissioning_status"] = self.dehydrate_test_statuses(
                    commissioning_script_results
                )
                data["commissioning_start_time"] = dehydrate_datetime(
                    commissioning_start_time
                )
                data["testing_status"] = self.dehydrate_test_statuses(
                    testing_script_results
                )
                data["has_logs"] = (
                    log_results.difference(script_output_nsmap.keys()) == set()
                )
            else:
                all_test_results = []
                if obj.id in self._script_results_for_list:
                    for results in self._script_results_for_list[
                        obj.id
                    ].values():
                        all_test_results += results

                data["testing_status"] = self.dehydrate_test_statuses_for_list(
                    all_test_results
                )
        else:
            blockdevices = []

        if obj.enable_hw_sync:
            data.update(
                {
                    "last_sync": dehydrate_datetime(obj.last_sync),
                    "sync_interval": obj.sync_interval,
                    "next_sync": dehydrate_datetime(obj.next_sync),
                    "is_sync_healthy": obj.is_sync_healthy,
                }
            )
        else:
            for k in ("last_sync", "sync_interval", "next_sync"):
                if k in data:
                    del data[k]

        if obj.node_type != NODE_TYPE.DEVICE:
            # These values are not defined on a device.
            data["architecture"] = obj.architecture
            data["osystem"] = obj.osystem
            data["distro_series"] = obj.distro_series
            data["memory"] = obj.display_memory()
            data["status"] = obj.display_status()
            data["description"] = obj.description
            data["status_code"] = obj.status
            if hasattr(obj, "simple_status"):
                data["simple_status"] = obj.simple_status
            else:
                data[
                    "simple_status"
                ] = SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
                    obj.status, SIMPLIFIED_NODE_STATUS.OTHER
                )

        # Filters are only available on machines and devices.
        if not obj.is_controller:
            # For filters
            subnets = self.get_all_subnets(obj)
            data["fabrics"] = sorted(self.get_all_fabric_names(obj, subnets))
            data["spaces"] = sorted(self.get_all_space_names(subnets))
            data["extra_macs"] = sorted(
                "%s" % mac_address for mac_address in obj.get_extra_macs()
            )
            if not for_list:
                data["subnets"] = sorted(subnet.cidr for subnet in subnets)
                data["link_speeds"] = sorted(
                    {
                        interface.link_speed
                        for interface in obj.current_config.interface_set.all()
                        if interface.link_speed > 0
                    }
                )

        if not for_list:
            for attr in ("numa_nodes_count", "sriov_support"):
                value = getattr(obj, attr, None)
                if value is not None:
                    data[attr] = value
            data["node_type_display"] = obj.get_node_type_display()
            data["on_network"] = obj.on_network()
            if obj.node_type != NODE_TYPE.DEVICE:
                data["numa_nodes"] = [
                    self.dehydrate_numanode(numa_node)
                    for numa_node in obj.numanode_set.all()
                ]
                # XXX lamont 2017-02-15 Much of this should be split out into
                # individual methods, rather than having this huge block of
                # dense code here.
                # Status of the commissioning, testing, and logs tabs
                data["metadata"] = {
                    metadata.key: metadata.value
                    for metadata in obj.nodemetadata_set.all()
                }

                # Network
                data["interfaces"] = [
                    self.dehydrate_interface(interface, obj)
                    for interface in obj.current_config.interface_set.all()
                ]
                data["dhcp_on"] = self.get_providing_dhcp(obj)

                data["hwe_kernel"] = make_hwe_kernel_ui_text(obj.hwe_kernel)

                data["power_type"] = obj.power_type
                data["power_parameters"] = self.dehydrate_power_parameters(
                    obj.get_power_parameters()
                )
                data["power_bmc_node_count"] = (
                    obj.bmc.node_set.count() if (obj.bmc is not None) else 0
                )

                # Storage
                data["disks"] = sorted(
                    chain(
                        (
                            self.dehydrate_blockdevice(blockdevice, obj)
                            for blockdevice in blockdevices
                        ),
                        (
                            self.dehydrate_volume_group(volume_group)
                            for volume_group in VolumeGroup.objects.filter_by_node(
                                obj
                            )
                        ),
                        (
                            self.dehydrate_cache_set(cache_set)
                            for cache_set in CacheSet.objects.get_cache_sets_for_node(
                                obj
                            )
                        ),
                    ),
                    key=itemgetter("name"),
                )
                data["supported_filesystems"] = [
                    {"key": key, "ui": ui}
                    for key, ui in FILESYSTEM_FORMAT_TYPE_CHOICES
                ]
                data["storage_layout_issues"] = obj.storage_layout_issues()
                data["special_filesystems"] = [
                    self.dehydrate_filesystem(filesystem)
                    for filesystem in obj.get_effective_special_filesystems()
                ]
                data["grouped_storages"] = self.get_grouped_storages(
                    physical_blockdevices
                )
                (
                    layout_bd,
                    detected_layout,
                ) = get_applied_storage_layout_for_node(obj)
                data["detected_storage_layout"] = detected_layout
                # The UI knows that a partition is in use when it has a mounted
                # partition. VMware ESXi does not directly mount the partitions
                # used. As MAAS can't model that inject a place holder so the
                # UI knows that these partitions are in use.
                datastore_partition_for_layout = {
                    "vmfs6": "-part3",
                    "vmfs7": "-part8",
                }.get(detected_layout)
                if datastore_partition_for_layout is not None:
                    for disk in data["disks"]:
                        if disk["id"] == layout_bd.id:
                            for partition in disk["partitions"]:
                                if partition["name"].endswith(
                                    datastore_partition_for_layout
                                ):
                                    # This partition may be modified by the
                                    # user.
                                    continue
                                partition[
                                    "used_for"
                                ] = "VMware ESXi OS partition"
                                partition["filesystem"] = {
                                    "id": -1,
                                    "label": "RESERVED",
                                    "mount_point": "RESERVED",
                                    "mount_options": None,
                                    "fstype": None,
                                    "is_format_fstype": False,
                                }
                # Events
                data["events"] = self.dehydrate_events(obj)

                # Machine logs
                data["installation_status"] = self.dehydrate_script_set_status(
                    obj.current_installation_script_set
                )

                # Third party drivers
                if Config.objects.get_config("enable_third_party_drivers"):
                    # Pull modaliases from the cache
                    modaliases = []
                    for script_result in commissioning_script_results:
                        if script_result.name == LIST_MODALIASES_OUTPUT_NAME:
                            if script_result.status == SCRIPT_STATUS.PASSED:
                                # STDOUT is deferred in the cache so load it.
                                script_result = (
                                    ScriptResult.objects.filter(
                                        id=script_result.id
                                    )
                                    .only("id", "status", "stdout")
                                    .first()
                                )
                                modaliases = script_result.stdout.decode(
                                    "utf-8"
                                ).splitlines()
                    driver = get_third_party_driver(
                        obj,
                        detected_aliases=modaliases,
                        series=obj.distro_series,
                    )
                    if "module" in driver and "comment" in driver:
                        data["third_party_driver"] = {
                            "module": driver["module"],
                            "comment": driver["comment"],
                        }

        return data

    def _cache_script_results_for_list(self, nodes):
        """
        Refresh the script results status cache for the machine list action.
        """

        if nodes is None or not len(nodes):
            return

        script_results_subquery = (
            ScriptResult.objects.filter(script_set__node__in=nodes)
            .order_by(
                "script_name",
                "physical_blockdevice_id",
                "interface_id",
                "script_set__node_id",
                "-id",
            )
            .distinct(
                "script_name",
                "physical_blockdevice_id",
                "interface_id",
                "script_set__node_id",
            )
            .values("id")
        )

        script_results_with_status_summary = (
            ScriptResult.objects.filter(
                id__in=Subquery(script_results_subquery)
            )
            .values_list("script_set__node_id", "script__hardware_type")
            .annotate(statuses=ArrayAgg("status", distinct=True))
        )

        self._script_results_for_list = {}
        for (
            node_id,
            hardware_type,
            statuses,
        ) in script_results_with_status_summary:
            if node_id not in self._script_results_for_list:
                self._script_results_for_list[node_id] = {}
            self._script_results_for_list[node_id][hardware_type] = statuses

    def _cache_script_results(self, nodes):
        """Refresh the ScriptResult cache from the given node."""
        script_results = (
            ScriptResult.objects.filter(script_set__node__in=nodes)
            .defer(
                "parameters",
                "output",
                "stdout",
                "stderr",
                "result",
                "script_set__tags",
                "script__results",
                "script__parameters",
                "script__packages",
            )
            .select_related("script_set", "script")
            .order_by(
                "script_name",
                "physical_blockdevice_id",
                "interface_id",
                "script_set__node_id",
                "-id",
            )
            .distinct(
                "script_name",
                "physical_blockdevice_id",
                "interface_id",
                "script_set__node_id",
            )
        )
        nodes_reset = set()
        for script_result in script_results:
            node_id = script_result.script_set.node_id
            if script_result.script is not None:
                hardware_type = script_result.script.hardware_type
            else:
                hardware_type = HARDWARE_TYPE.NODE

            # _cache_script_results is only called once per list(), get()
            # Postgres trigger update. Make sure the cache is cleared for the
            # node so if list(), get(), or a trigger is called multiple times
            # with the same instance of NodesHandler() only one set of results
            # is stored.
            if node_id not in nodes_reset:
                self._script_results[node_id] = {}
                nodes_reset.add(node_id)

            if hardware_type not in self._script_results[node_id]:
                self._script_results[node_id][hardware_type] = []

            if script_result.status == SCRIPT_STATUS.ABORTED:
                # LP:1724235, LP:1731350 - Ignore aborted results and make
                # sure results which were previous not aborted have been
                # cleared from the cache. This allows users to abort
                # commissioning/testing and have the status transition from
                # pending to None.
                for i, cached_script_result in enumerate(
                    self._script_results[node_id][hardware_type]
                ):
                    if cached_script_result.id == script_result.id:
                        self._script_results[node_id][hardware_type].pop(i)
                        break
            else:
                self._script_results[node_id][hardware_type].append(
                    script_result
                )

    def _load_extra_data_before_dehydrate(self, nodes, for_list=False):
        if not for_list:
            self._cache_script_results(nodes)
        else:
            # For the list action we don't need to retrieve the entire
            # script results objects. We just need the statuses. This is why we
            # use a dedicated query to retrieve such information, reducing
            # network traffic and increasing the performances.
            self._cache_script_results_for_list(nodes)

    def on_listen_for_active_pk(self, action, pk, obj):
        self._cache_script_results([obj])
        return super().on_listen_for_active_pk(action, pk, obj)

    def dehydrate_blockdevice(self, blockdevice, obj):
        """Return `BlockDevice` formatted for JSON encoding."""
        # model and serial are currently only avalible on physical block
        # devices
        if isinstance(blockdevice, PhysicalBlockDevice):
            model = blockdevice.model
            serial = blockdevice.serial
            firmware_version = blockdevice.firmware_version
        else:
            serial = model = firmware_version = ""
        partition_table = blockdevice.get_partitiontable()
        if partition_table is not None:
            partition_table_type = partition_table.table_type
        else:
            partition_table_type = ""
        is_boot = False
        boot_disk = obj.get_boot_disk()
        # there might not be any disk usable as boot disk
        if boot_disk:
            is_boot = blockdevice.id == boot_disk.id
        numa_node_index = (
            blockdevice.numa_node.index
            if hasattr(blockdevice, "numa_node")
            else None
        )
        data = {
            "id": blockdevice.id,
            "is_boot": is_boot,
            "name": blockdevice.get_name(),
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "used_size": blockdevice.used_size,
            "available_size": blockdevice.available_size,
            "block_size": blockdevice.block_size,
            "model": model,
            "serial": serial,
            "firmware_version": firmware_version,
            "partition_table_type": partition_table_type,
            "used_for": blockdevice.used_for,
            "filesystem": self.dehydrate_filesystem(
                blockdevice.get_effective_filesystem()
            ),
            "partitions": self.dehydrate_partitions(
                blockdevice.get_partitiontable()
            ),
            "numa_node": numa_node_index,
        }
        if isinstance(blockdevice, VirtualBlockDevice):
            data["parent"] = {
                "id": blockdevice.filesystem_group.id,
                "uuid": blockdevice.filesystem_group.uuid,
                "type": blockdevice.filesystem_group.group_type,
            }
        # Calculate script results status for blockdevice
        # if a physical block device.
        blockdevice_script_results = [
            script_result
            for results in self._script_results.values()
            for script_results in results.values()
            for script_result in script_results
            if script_result.physical_blockdevice_id == blockdevice.id
        ]
        data["test_status"] = get_status_from_qs(blockdevice_script_results)

        return data

    def dehydrate_volume_group(self, volume_group):
        """Return `VolumeGroup` formatted for JSON encoding."""
        size = volume_group.get_size()
        available_size = volume_group.get_lvm_free_space()
        used_size = volume_group.get_lvm_allocated_size()
        return {
            "id": volume_group.id,
            "name": volume_group.name,
            "tags": [],
            "type": volume_group.group_type,
            "path": "",
            "size": size,
            "used_size": used_size,
            "available_size": available_size,
            "block_size": volume_group.get_virtual_block_device_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": "volume group",
            "filesystem": None,
            "partitions": None,
            "numa_nodes": volume_group.get_numa_node_indexes(),
        }

    def dehydrate_cache_set(self, cache_set):
        """Return `CacheSet` formatted for JSON encoding."""
        device = cache_set.get_device()
        used_size = device.get_used_size()
        available_size = device.get_available_size()
        bcache_devices = sorted(
            bcache.name for bcache in cache_set.filesystemgroup_set.all()
        )
        return {
            "id": cache_set.id,
            "name": cache_set.name,
            "tags": [],
            "type": "cache-set",
            "path": "",
            "size": device.size,
            "used_size": used_size,
            "available_size": available_size,
            "block_size": device.get_block_size(),
            "model": "",
            "serial": "",
            "partition_table_type": "",
            "used_for": ", ".join(bcache_devices),
            "filesystem": None,
            "partitions": None,
            "numa_nodes": cache_set.get_numa_node_indexes(),
        }

    def dehydrate_partitions(self, partition_table):
        """Return `PartitionTable` formatted for JSON encoding."""
        if partition_table is None:
            return None
        partitions = []
        for partition in partition_table.partitions.all():
            partitions.append(
                {
                    "filesystem": self.dehydrate_filesystem(
                        partition.get_effective_filesystem()
                    ),
                    "name": partition.get_name(),
                    "path": partition.path,
                    "type": partition.type,
                    "id": partition.id,
                    "size": partition.size,
                    "used_for": partition.used_for,
                    "tags": partition.tags,
                }
            )
        return partitions

    def dehydrate_filesystem(self, filesystem):
        """Return `Filesystem` formatted for JSON encoding."""
        if filesystem is None:
            return None
        return {
            "id": filesystem.id,
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
            "mount_options": filesystem.mount_options,
            "fstype": filesystem.fstype,
            "is_format_fstype": (
                filesystem.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT
            ),
        }

    def dehydrate_interface(self, interface, obj):
        """Dehydrate a `interface` into a interface definition."""
        # Sort the links by ID that way they show up in the same order in
        # the UI.
        links = sorted(interface.get_links(), key=itemgetter("id"))
        for link in links:
            # Replace the subnet object with the subnet_id. The client will
            # use this information to pull the subnet information from the
            # websocket.
            subnet = link.pop("subnet", None)
            if subnet is not None:
                link["subnet_id"] = subnet.id
        numa_node_index = (
            interface.numa_node.index if interface.numa_node else None
        )
        data = {
            "id": interface.id,
            "type": interface.type,
            "name": interface.name,
            "enabled": interface.is_enabled(),
            "tags": interface.tags,
            "is_boot": interface == obj.get_boot_interface(),
            "mac_address": "%s" % interface.mac_address,
            "vlan_id": interface.vlan_id,
            "params": interface.params,
            "parents": [nic.id for nic in interface.parents.all()],
            "children": [
                nic.child.id for nic in interface.children_relationships.all()
            ],
            "links": links,
            "interface_speed": interface.interface_speed,
            "link_connected": interface.link_connected,
            "link_speed": interface.link_speed,
            "numa_node": numa_node_index,
            "vendor": interface.vendor,
            "product": interface.product,
            "firmware_version": interface.firmware_version,
            "sriov_max_vf": interface.sriov_max_vf,
        }

        # When the node is an ephemeral state display the discovered IP address
        # for this interface. This will only be shown on interfaces that are
        # connected to a MAAS managed subnet.
        if obj.status in {
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.EXITING_RESCUE_MODE,
            NODE_STATUS.TESTING,
        } or (
            obj.status == NODE_STATUS.FAILED_TESTING
            and obj.power_state == POWER_STATE.ON
        ):
            discovereds = interface.get_discovered()
            # Work around bug #1717511. Bond's don't get configured, so
            # any of the bond's physical interface might have gotten an
            # IP.
            if not discovereds and interface.type == INTERFACE_TYPE.BOND:
                for parent in interface.parents.all():
                    discovereds = parent.get_discovered()
                    if discovereds:
                        break
            if discovereds is not None:
                for discovered in discovereds:
                    # Replace the subnet object with the subnet_id. The client
                    # will use this information to pull the subnet information
                    # from the websocket.
                    discovered["subnet_id"] = discovered.pop("subnet").id
                data["discovered"] = discovereds

        return data

    def dehydrate_vlan(self, obj, interface):
        """Return the fabric and VLAN for the interface."""
        if interface is None:
            return None

        if interface.vlan is not None:
            return {
                "id": interface.vlan_id,
                "name": interface.vlan.name if interface.vlan.name else "",
                "fabric_id": interface.vlan.fabric.id,
                "fabric_name": "%s" % interface.vlan.fabric.name,
            }

    def dehydrate_all_ip_addresses(self, obj):
        """Return all IP addresses for a machine"""
        # If the node has static IP addresses assigned they will be returned
        # before the dynamic IP addresses are returned. The dynamic IP
        # addresses will only be returned if the node has no static IP
        # addresses.

        boot_interface = obj.get_boot_interface()

        ip_addresses = [
            {"ip": ip_address.get_ip(), "is_boot": interface == boot_interface}
            for interface in sorted(
                obj.current_config.interface_set.all(), key=attrgetter("name")
            )
            for ip_address in interface.ip_addresses.all()
            if ip_address.ip
            and ip_address.alloc_type
            in [
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
            ]
        ]

        if len(ip_addresses) == 0:
            ip_addresses = [
                {"ip": ip_address.ip, "is_boot": interface == boot_interface}
                for interface in sorted(
                    obj.current_config.interface_set.all(),
                    key=attrgetter("name"),
                )
                for ip_address in interface.ip_addresses.all()
                if (
                    ip_address.ip
                    and ip_address.alloc_type == IPADDRESS_TYPE.DISCOVERED
                )
            ]

        return ip_addresses

    def dehydrate_ip_address(self, obj, interface):
        """Return the IP address for the interface of a device."""
        if interface is None:
            return None

        # Get ip address from StaticIPAddress if available.
        ip_addresses = list(interface.ip_addresses.all())
        first_ip = self._get_first_non_discovered_ip(ip_addresses)
        if first_ip is not None:
            if first_ip.alloc_type == IPADDRESS_TYPE.DHCP:
                discovered_ip = self._get_first_discovered_ip_with_ip(
                    ip_addresses
                )
                if discovered_ip:
                    return "%s" % discovered_ip.ip
            elif first_ip.ip:
                return "%s" % first_ip.ip
        # Currently has no assigned IP address.
        return None

    def _get_first_non_discovered_ip(self, ip_addresses):
        for ip in ip_addresses:
            if ip.alloc_type != IPADDRESS_TYPE.DISCOVERED:
                return ip

    def _get_first_discovered_ip_with_ip(self, ip_addresses):
        for ip in ip_addresses:
            if ip.alloc_type == IPADDRESS_TYPE.DISCOVERED and ip.ip:
                return ip

    def dehydrate_script_set_status(self, obj):
        """Dehydrate the script set status."""
        if obj is None:
            return -1
        else:
            return obj.status

    def dehydrate_events(self, obj):
        """Dehydrate the node events.

        The latests 50 not including DEBUG events will be dehydrated. The
        `EventsHandler` needs to be used if more are required.
        """
        events = (
            Event.objects.filter(node=obj)
            .exclude(type__level=logging.DEBUG)
            .select_related("type")
            .order_by("-id")[:50]
        )
        return [
            {
                "id": event.id,
                "type": {
                    "id": event.type.id,
                    "name": event.type.name,
                    "description": event.type.description,
                    "level": dehydrate_event_type_level(event.type.level),
                },
                "description": event.description,
                "created": dehydrate_datetime(event.created),
            }
            for event in events
        ]

    def preprocess_node_form(self, action, params):
        """Helper for sub-classes to deal with common parameters."""
        new_params = {}
        new_params["description"] = params.get("description")
        if "zone" in params:
            new_params["zone"] = params["zone"]["name"]
        if "domain" in params:
            new_params["domain"] = params["domain"]["name"]
        return new_params

    def get_all_storage_tags(self, blockdevices):
        """Return list of all storage tags in `blockdevices`."""
        tags = set()
        for blockdevice in blockdevices:
            tags = tags.union(blockdevice.tags)
            partition_table = blockdevice.get_partitiontable()
            if partition_table is not None:
                for partition in partition_table.partitions.all():
                    tags = tags.union(partition.tags)
        return list(tags)

    def get_all_subnets(self, obj):
        subnets = set()
        for interface in obj.current_config.interface_set.all():
            for ip_address in interface.ip_addresses.all():
                if ip_address.subnet is not None:
                    subnets.add(ip_address.subnet)
        return list(subnets)

    def get_all_fabric_names(self, obj, subnets):
        fabric_names = set()
        for interface in obj.current_config.interface_set.all():
            if interface.vlan is not None:
                fabric_names.add(interface.vlan.fabric.name)
        for subnet in subnets:
            fabric_names.add(subnet.vlan.fabric.name)
        return list(fabric_names)

    def get_all_space_names(self, subnets):
        space_names = set()
        for subnet in subnets:
            if subnet.vlan.space is not None:
                space_names.add(subnet.vlan.space.name)
        return list(space_names)

    def get_blockdevices_for(self, obj):
        """Return only `BlockDevice`s using the prefetched query."""
        return [
            blockdevice.actual_instance
            for blockdevice in obj.current_config.blockdevice_set.all()
        ]

    def get_providing_dhcp(self, obj):
        """Return if providing DHCP using the prefetched query."""
        for interface in obj.current_config.interface_set.all():
            if interface.vlan is not None:
                if interface.vlan.dhcp_on:
                    return True
        return False

    def get_grouped_storages(self, blockdevices):
        """Group storage based off of the size and type.

        This is used by the storage card when displaying the grouped disks.
        """
        disk_data = [
            (blockdevice.size, "hdd" if disk_type == "rotary" else disk_type)
            for blockdevice in blockdevices
            for disk_type in ("ssd", "hdd", "rotary")
            if disk_type in blockdevice.tags
        ]
        grouped_storages = []
        for disk_type in ("ssd", "hdd", "rotary"):
            c = Counter(elem[0] for elem in disk_data if elem[1] == disk_type)
            for size, count in c.items():
                grouped_storages.append(
                    {"size": size, "count": count, "disk_type": disk_type}
                )
        return grouped_storages

    def get_summary_xml(self, params):
        """Return the node summary XML formatted."""
        node = self.get_object(params)
        # Produce a "clean" composite details document.
        details_template = dict.fromkeys(script_output_nsmap.values())
        for script_result in (
            node.get_latest_script_results.filter(
                script_name__in=script_output_nsmap.keys(),
                status=SCRIPT_STATUS.PASSED,
                script_set__node=node,
            )
            .only(
                "status",
                "script_name",
                "updated",
                "stdout",
                "script__id",
                "script_set__node",
                "script__name",
            )
            .order_by("script_name", "-updated")
            .distinct("script_name")
        ):
            namespace = script_output_nsmap[script_result.name]
            details_template[namespace] = script_result.stdout
        probed_details = merge_details_cleanly(details_template)

        # We check here if there's something to show instead of after
        # the call to get_single_probed_details() because here the
        # details will be guaranteed well-formed.
        if len(probed_details.xpath("/*/*")) == 0:
            return ""
        else:
            return etree.tostring(
                probed_details, encoding=str, pretty_print=True
            )

    def get_summary_yaml(self, params):
        """Return the node summary YAML formatted."""
        node = self.get_object(params)
        # Produce a "clean" composite details document.
        details_template = dict.fromkeys(script_output_nsmap.values())
        for script_result in (
            ScriptResult.objects.filter(
                script_name__in=script_output_nsmap.keys(),
                status=SCRIPT_STATUS.PASSED,
                script_set__node=node,
            )
            .only(
                "status",
                "script_name",
                "updated",
                "stdout",
                "script__id",
                "script_set__node",
            )
            .order_by("script_name", "-updated")
            .distinct("script_name")
        ):
            namespace = script_output_nsmap[script_result.name]
            details_template[namespace] = script_result.stdout
        probed_details = merge_details_cleanly(details_template)

        # We check here if there's something to show instead of after
        # the call to get_single_probed_details() because here the
        # details will be guaranteed well-formed.
        if len(probed_details.xpath("/*/*")) == 0:
            return ""
        else:
            return XMLToYAML(
                etree.tostring(probed_details, encoding=str, pretty_print=True)
            ).convert()

    def set_script_result_suppressed(self, params):
        """Set suppressed for the ScriptResult ids."""
        node = self.get_object(params, NodePermission.admin)
        script_result_ids = params.get("script_result_ids")
        ScriptResult.objects.filter(
            script_set__node__system_id=node.system_id,
            id__in=script_result_ids,
        ).update(suppressed=True)

    def set_script_result_unsuppressed(self, params):
        """Set unsuppressed for the ScriptResult ids."""
        node = self.get_object(params, NodePermission.admin)
        script_result_ids = params.get("script_result_ids")
        ScriptResult.objects.filter(
            script_set__node__system_id=node.system_id,
            id__in=script_result_ids,
        ).update(suppressed=False)

    def _get_latest_failed_testing_script_results(
        self, system_ids: Iterable[str]
    ) -> Iterable[ScriptResult]:
        script_results = (
            ScriptResult.objects.filter(
                script_set__node__system_id__in=system_ids,
                script_set__result_type=RESULT_TYPE.TESTING,
            )
            .prefetch_related("script", "script_set", "script_set__node")
            .defer(
                "output",
                "stdout",
                "stderr",
                "script__parameters",
                "script__packages",
                "script_set__tags",
            )
            .order_by(
                "script_set__node_id",
                "script_name",
                "physical_blockdevice_id",
                "-id",
            )
            .distinct(
                "script_set__node_id", "script_name", "physical_blockdevice_id"
            )
        )
        node_script_results = [
            s for s in script_results if s.status in SCRIPT_STATUS_FAILED
        ]
        return node_script_results

    def get_latest_failed_testing_script_results(self, params):
        """Return a dictionary with Nodes system_ids mapped to a list of
        the latest failed ScriptResults."""
        node_result_handler = NodeResultHandler(self.user, {}, None)
        if "filter" in params:
            qs = self.get_queryset(for_list=True)
            system_ids = self._filter(
                qs, "list", params.get("filter")
            ).values_list("system_id", flat=True)
        else:
            system_ids = params.get("system_ids")

        script_results = self._get_latest_failed_testing_script_results(
            system_ids
        )
        script_result_mappings = {}
        for script_result in script_results:
            system_id = script_result.script_set.node.system_id
            mapping = node_result_handler.dehydrate(
                script_result, {}, for_list=True
            )
            mapping["id"] = script_result.id
            script_result_mappings.setdefault(system_id, []).append(mapping)
        return script_result_mappings

    def _update_tags(self, node, tag_ids):
        tags = list(Tag.objects.filter(id__in=tag_ids))
        for tag in tags:
            if tag.is_defined:
                raise HandlerError(
                    f"Cannot add tag {tag.name} to node because it has a definition"
                )
        node.tags.set(tags)

    def _filter(self, qs, action, params):
        qs = super()._filter(qs, action, params)
        form = FreeTextFilterNodeForm(data=params)
        if not form.is_valid():
            raise HandlerValidationError(form.errors)
        qs, _, _ = form.filter_nodes(qs)
        return qs

    def _get_group_expr(self, key):
        """Get grouping expression for key"""
        if key == "pod":
            expr = "bmc__name"
        elif key == "pod_type":
            expr = "bmc__power_type"
        elif key == "pool":
            expr = "pool__name"
        elif key == "domain":
            expr = "domain__name"
        elif key == "zone":
            expr = "zone__name"
        elif key == "owner":
            expr = "owner__username"
        elif key == "fqdn":
            expr = "node_fqdn"
        elif key == "storage":
            expr = "total_storage"
        elif key == "parent":
            expr = "parent__hostname"
        else:
            expr = key
        return expr

    def _get_group_label(self, key, value):
        """Get grouping expression for key"""
        if key == "power_state":
            return getattr(POWER_STATE, value.upper()).capitalize()
        elif key == "status":
            return NODE_STATUS_CHOICES_DICT[value]
        elif key == "simple_status":
            return SIMPLIFIED_NODE_STATUS_CHOICES_DICT[value]
        else:
            return super()._get_group_label(key, value)

    def _get_group_value(self, key, value):
        """Get grouping expression for key"""
        if key == "status":
            stat = map_enum_reverse(NODE_STATUS, ignore=["DEFAULT"])
            return stat[value].lower()
        elif key == "simple_status":
            stat = map_enum_reverse(SIMPLIFIED_NODE_STATUS, ignore=["DEFAULT"])
            return stat[value].lower()
        else:
            return value

    def _xlate_group_id(self, key, value):
        if key == "power_state":
            return getattr(POWER_STATE, value.upper())
        elif key == "status":
            return getattr(NODE_STATUS, value.upper())
        elif key == "simple_status":
            return getattr(SIMPLIFIED_NODE_STATUS, value.upper())
        else:
            return value

    def filter_groups(self, params):
        """List available fields to filter on"""
        suppress = [
            "free_text",
            "id",
            "not_id",
            "hostname",
            "not_hostname",
            "description",
            "error_description",
        ]
        return [
            {
                "key": name,
                "label": field.label,
                "type": get_field_argument_type(field),
                "dynamic": name not in STATIC_FILTER_FIELDS,
                "for_grouping": name in GROUPABLE_FIELDS,
            }
            for name, field in FreeTextFilterNodeForm.declared_fields.items()
            if name not in suppress
        ]

    def _get_dynamic_filter_options(self, key):
        results = []
        if key == "tags":
            return [
                {"key": tag, "label": tag}
                for tag in Tag.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "fabrics":
            results += [
                {"key": value, "label": value}
                for value in Fabric.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "fabric_classes":
            results += [
                {"key": fabric, "label": fabric}
                for fabric in Fabric.objects.filter(class_type__isnull=False)
                .order_by("class_type")
                .values_list("class_type", flat=True)
                .distinct()
            ]
        elif key == "subnets":
            results += [
                {"key": value.cidr, "label": value.name}
                for value in Subnet.objects.order_by("name")
            ]
        elif key == "vlans":
            results += [
                {"key": value, "label": value}
                for value in VLAN.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "link_speed":
            results += [
                {"key": link_speed, "label": human_readable_bytes(link_speed)}
                for link_speed in Interface.objects.order_by("link_speed")
                .values_list("link_speed", flat=True)
                .distinct()
            ]
        elif key == "storage":
            results += [
                {"key": f"0({tag})", "label": tag}
                for values in BlockDevice.objects.order_by("tags")
                .values_list("tags", flat=True)
                .distinct()
                for tag in values
            ]
            results += [
                {"key": f"0(partition,{tag})", "label": f"{tag} (partition)"}
                for values in Partition.objects.order_by("tags")
                .values_list("tags", flat=True)
                .distinct()
                for tag in values
            ]
        elif key == "interfaces":
            for field in ["name", "type"]:
                results += [
                    {
                        "key": f"{field}={val}",
                        "label": f"{field}={val}",
                    }
                    for val in Interface.objects.order_by(field)
                    .values_list(field, flat=True)
                    .distinct()
                ]
            for field in ["tags"]:
                tags = [
                    val
                    for tags in Interface.objects.order_by(field)
                    .values_list(field, flat=True)
                    .distinct()
                    for val in tags
                ]
                results += [
                    {
                        "key": f"tag={val}",
                        "label": f"tag={val}",
                    }
                    for val in sorted(set(tags))
                ]
        elif key == "devices":
            for field in ["vendor_name", "product_name"]:
                results += [
                    {"key": f"{field}={val}", "label": f"{field}={val}"}
                    for val in NodeDevice.objects.order_by(field)
                    .values_list(field, flat=True)
                    .distinct()
                ]
        elif key == "mac_address":
            results += [
                {"key": str(val), "label": str(val).upper()}
                for val in Interface.objects.order_by("mac_address")
                .values_list("mac_address", flat=True)
                .distinct()
            ]
        elif key == "pod_type":
            results += [
                {"key": value, "label": value}
                for value in BMC.objects.order_by("power_type")
                .values_list("power_type", flat=True)
                .distinct()
            ]
        elif key == "pod":
            results += [
                {"key": pod, "label": pod}
                for pod in BMC.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "zone":
            results += [
                {"key": zone, "label": zone}
                for zone in Zone.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "pool":
            results += [
                {"key": pool, "label": pool}
                for pool in ResourcePool.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "owner":
            results += [
                {"key": user, "label": user}
                for user in User.objects.order_by("username")
                .values_list("username", flat=True)
                .distinct()
            ]
        elif key == "domain":
            results += [
                {"key": dom, "label": dom}
                for dom in Domain.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "id":
            results += [
                {"key": value.system_id, "label": value.system_id}
                for value in Node.objects.order_by("system_id")
            ]
        elif key == "ip_addresses":
            results += [
                {"key": value, "label": value}
                for value in StaticIPAddress.objects.order_by("ip")
                .values_list("ip", flat=True)
                .distinct()
            ]
        elif key == "spaces":
            results += [
                {"key": value, "label": value}
                for value in Space.objects.order_by("name")
                .values_list("name", flat=True)
                .distinct()
            ]
        elif key == "workloads":
            results += [
                {"key": f"{k}:{v}", "label": f"{k}: {v}"}
                for k, v in OwnerData.objects.order_by("key")
                .values_list("key", "value")
                .distinct()
            ]
        else:
            qs = self.get_queryset(for_list=True)
            key = self._get_group_expr(key)
            for value in qs.order_by(key).values_list(key).distinct():
                if isinstance(value, Iterable):
                    results += [{"key": v, "label": str(v)} for v in value]
                else:
                    results.append({"key": value, "label": str(value)})
        return results

    def filter_options(self, params):
        try:
            key = params["group_key"]
        except KeyError:
            raise HandlerValidationError(
                "a 'group_key' param must be provided for filter_options"
            )
        else:
            if key not in FreeTextFilterNodeForm.declared_fields.keys():
                raise HandlerValidationError(
                    f"{key} is not a valid 'group_key' for filter_options"
                )

            key = key.removeprefix("not_in_").removeprefix("not_")
            if key == "mem":
                key = "memory"
            if key == "fqdn":
                key = "node_fqdn"

            if key in STATIC_FILTER_FIELDS:
                if key == "arch":
                    return [
                        {"key": arch, "label": arch}
                        for arch in sorted(list_all_usable_architectures())
                    ]
                elif key == "status":
                    return [
                        {
                            "key": choice[0],
                            "label": NODE_STATUS_CHOICES_DICT[
                                getattr(NODE_STATUS, choice[0].upper())
                            ],
                        }
                        for choice in sorted(NODE_STATUS_SHORT_LABEL_CHOICES)
                    ]
                elif key == "simple_status":
                    return [
                        {
                            "key": choice[0],
                            "label": SIMPLIFIED_NODE_STATUS_CHOICES_DICT[
                                getattr(
                                    SIMPLIFIED_NODE_STATUS, choice[0].upper()
                                )
                            ],
                        }
                        for choice in sorted(
                            SIMPLIFIED_NODE_STATUS_LABEL_CHOICES
                        )
                    ]
                elif key == "power_state":
                    return [
                        {"key": choice[0], "label": choice[1]}
                        for choice in sorted(POWER_STATE_CHOICES)
                    ]
                elif key == "sriov_support":
                    return [
                        {"key": choice, "label": str(choice)}
                        for choice in (True, False)
                    ]
            else:
                return self._get_dynamic_filter_options(key)

    def update_interface(self, params):
        """Update the interface."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        interface = Interface.objects.get(
            node_config__node=node, id=params["interface_id"]
        )
        if node.is_controller:
            interface_form = ControllerInterfaceForm
        elif node.status == NODE_STATUS.DEPLOYED:
            interface_form = DeployedInterfaceForm
        else:
            interface_form = InterfaceForm.get_interface_form(interface.type)
        form = interface_form(instance=interface, data=params)
        if form.is_valid():
            interface = form.save()
            self._update_obj_tags(interface, params)
        else:
            raise ValidationError(form.errors)
        if "mode" in params:
            self.link_subnet(params)
        node.refresh_from_db()
        return self.full_dehydrate(node)

    def _get_node_or_permission_error(self, params, permission=None):
        node = self.get_object(params, permission=permission)
        if node.locked:
            raise HandlerPermissionError()
        return node

    def _update_obj_tags(self, obj, params):
        if "tags" in params:
            obj.tags = params["tags"]
            obj.save(update_fields=["tags"])

    def link_subnet(self, params):
        """Create or update the link."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        interface = Interface.objects.get(
            node_config__node=node, id=params["interface_id"]
        )
        subnet = None
        if "subnet" in params:
            subnet = Subnet.objects.get(id=params["subnet"])
        if "link_id" in params:
            if interface.ip_addresses.filter(id=params["link_id"]).exists():
                # We are updating an already existing link.  Which may have
                # been deleted.
                interface.update_link_by_id(
                    params["link_id"],
                    params["mode"],
                    subnet,
                    ip_address=params.get("ip_address", None),
                )
        else:
            # We are creating a new link.
            interface.link_subnet(
                params["mode"],
                subnet,
                ip_address=params.get("ip_address", None),
            )

    def unlink_subnet(self, params):
        """Delete the link."""
        node = self._get_node_or_permission_error(
            params, permission=self._meta.edit_permission
        )
        interface = Interface.objects.get(
            node_config__node=node, id=params["interface_id"]
        )
        interface.unlink_subnet_by_id(params["link_id"])
