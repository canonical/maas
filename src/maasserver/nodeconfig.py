from typing import Callable, Dict, Optional

from django.db.models import Model, Q
from django.utils import timezone

from maasserver.models import (
    CacheSet,
    FilesystemGroup,
    NodeConfig,
    Partition,
    PartitionTable,
    PhysicalBlockDevice,
    VirtualBlockDevice,
)
from maasserver.models.interface import InterfaceRelationship
from maasserver.models.virtualmachine import (
    VirtualMachineDisk,
    VirtualMachineInterface,
)


def duplicate_nodeconfig(src_config: NodeConfig, dest_type: str) -> NodeConfig:
    """Create a NodeConfig of the specified type as a copy of the source one."""
    dest_node_config = NodeConfig.objects.create(
        name=dest_type, node_id=src_config.node_id
    )

    def process_interface(entry):
        entry.node_config = dest_node_config

    interface_map = _duplicate_entry_set(
        src_config.interface_set.all(),
        process_interface,
    )
    orig_interface_ids = list(interface_map)
    # create parent-child relationships
    now = timezone.now()
    InterfaceRelationship.objects.bulk_create(
        InterfaceRelationship(
            parent_id=interface_map[parent_id],
            child_id=interface_map[child_id],
            created=now,
            updated=now,
        )
        for parent_id, child_id in InterfaceRelationship.objects.filter(
            Q(parent_id__in=orig_interface_ids)
            | Q(child_id__in=orig_interface_ids)
        ).values_list("parent_id", "child_id")
    )

    def process_virtualmachineinterface(viface):
        viface.host_interface_id = interface_map.get(viface.host_interface_id)

    _duplicate_entry_set(
        VirtualMachineInterface.objects.filter(
            host_interface_id__in=interface_map
        ),
        process_virtualmachineinterface,
    )

    # XXX handle IP addressed linked to interface

    blockdevice_map = {}

    def process_blockdevice(bdev):
        bdev.blockdevice_ptr_id = None
        bdev.node_config = dest_node_config

    blockdevice_map.update(
        _duplicate_entry_set(
            PhysicalBlockDevice.objects.filter(node_config=src_config),
            process_blockdevice,
        )
    )

    cacheset_map = _duplicate_entry_set(
        CacheSet.objects.filter(filesystems__node_config=src_config)
    )

    def process_filesystemgroup(fsgroup):
        fsgroup.cache_set_id = cacheset_map.get(fsgroup.cache_set_id)

    filesystemgroup_map = _duplicate_entry_set(
        FilesystemGroup.objects.filter(
            virtual_devices__node_config=src_config
        ),
        process_filesystemgroup,
    )

    def process_virtualblockdevice(dev):
        process_blockdevice(dev)
        dev.filesystem_group_id = filesystemgroup_map[dev.filesystem_group_id]

    blockdevice_map.update(
        _duplicate_entry_set(
            VirtualBlockDevice.objects.filter(node_config=src_config),
            process_virtualblockdevice,
        )
    )

    def process_partition_table(ptable):
        ptable.block_device_id = blockdevice_map[ptable.block_device_id]

    ptable_map = _duplicate_entry_set(
        PartitionTable.objects.filter(block_device_id__in=blockdevice_map),
        process_partition_table,
    )

    def process_partition(partition):
        partition.partition_table_id = ptable_map[partition.partition_table_id]

    partition_map = _duplicate_entry_set(
        Partition.objects.filter(partition_table_id__in=ptable_map),
        process_partition,
    )

    def process_filesystem(fs):
        fs.node_config = dest_node_config
        fs.filesystem_group_id = filesystemgroup_map.get(
            fs.filesystem_group_id
        )
        fs.cache_set_id = cacheset_map.get(fs.cache_set_id)
        fs.partition_id = partition_map.get(fs.partition_id)
        fs.block_device_id = blockdevice_map.get(fs.block_device_id)

    _duplicate_entry_set(
        src_config.filesystem_set.all(),
        process_filesystem,
    )

    def process_nodedevice(device):
        device.node_config = dest_node_config
        device.physical_blockdevice_id = blockdevice_map.get(
            device.physical_blockdevice_id
        )
        device.physical_interface_id = interface_map.get(
            device.physical_interface_id
        )

    _duplicate_entry_set(
        src_config.nodedevice_set.all(),
        process_nodedevice,
    )

    def process_virtualmachinedisk(vdisk):
        vdisk.block_device_id = blockdevice_map.get(vdisk.block_device_id)

    _duplicate_entry_set(
        VirtualMachineDisk.objects.filter(block_device_id__in=blockdevice_map),
        process_virtualmachinedisk,
    )

    return dest_node_config


def _duplicate_entry_set(
    queryset, process_entry: Optional[Callable] = None
) -> Dict[int, int]:
    """ "Duplicate entries in the queryset, optionally further processing them."""
    entry_map = {}
    for entry in queryset:
        orig_id, entry.id = entry.id, None
        if process_entry:
            process_entry(entry)
        # call the base class method to skip CleanSave validation. This is
        # needed since it would otherwise be necessary to create nested models
        # (e.g. storage devices) in order.
        Model.save(entry)
        entry_map[orig_id] = entry.id

    return entry_map
