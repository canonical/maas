import {
  canBeDeleted,
  canBeFormatted,
  canBePartitioned,
  canCreateBcache,
  canCreateCacheSet,
  canCreateLogicalVolume,
  canCreateOrUpdateDatastore,
  canCreateRaid,
  canCreateVolumeGroup,
  canOsSupportBcacheZFS,
  canOsSupportStorageConfig,
  canSetBootDisk,
  diskAvailable,
  formatSize,
  formatType,
  getDiskById,
  getNextStorageName,
  getPartitionById,
  isBcache,
  isCacheSet,
  isDatastore,
  isDisk,
  isFormatted,
  isLogicalVolume,
  isMounted,
  isNodeStorageConfigurable,
  isPartition,
  isPhysical,
  isRaid,
  isVirtual,
  isVMWareLayout,
  isVolumeGroup,
  partitionAvailable,
  splitDiskPartitionIds,
  usesStorage,
} from "./storage";

import { MIN_PARTITION_SIZE } from "@/app/store/machine/constants";
import { DiskTypes, StorageLayout } from "@/app/store/types/enum";
import { NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("canBeDeleted", () => {
  it("handles null case", () => {
    expect(canBeDeleted(null)).toBe(false);
  });

  it("returns whether a volume group can be deleted", () => {
    const deletable = factory.nodeDisk({
      type: DiskTypes.VOLUME_GROUP,
      used_size: 0,
    });
    const nonDeletable = factory.nodeDisk({
      type: DiskTypes.VOLUME_GROUP,
      used_size: 1000,
    });
    expect(canBeDeleted(deletable)).toBe(true);
    expect(canBeDeleted(nonDeletable)).toBe(false);
  });

  it("returns whether a non-volume group disk can be deleted", () => {
    const deletable = factory.nodeDisk({
      type: DiskTypes.PHYSICAL,
      partitions: [],
    });
    const nonDeletable = factory.nodeDisk({
      type: DiskTypes.PHYSICAL,
      partitions: [factory.nodePartition()],
    });
    expect(canBeDeleted(deletable)).toBe(true);
    expect(canBeDeleted(nonDeletable)).toBe(false);
  });
});

describe("canBeFormatted", () => {
  it("handles null case", () => {
    expect(canBeFormatted(null)).toBe(false);
  });

  it("returns whether a filesystem can be formatted", () => {
    const formattable = factory.nodeFilesystem({ is_format_fstype: true });
    const notFormattable = factory.nodeFilesystem({ is_format_fstype: false });
    expect(canBeFormatted(formattable)).toBe(true);
    expect(canBeFormatted(notFormattable)).toBe(false);
  });
});

describe("canBePartitioned", () => {
  it("handles null case", () => {
    expect(canBePartitioned(null)).toBe(false);
  });

  it("handles physical disks with available space", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.PHYSICAL,
    });
    expect(canBePartitioned(disk)).toBe(true);
  });

  it("handles formatted disks", () => {
    const disk = factory.nodeDisk({
      filesystem: factory.nodeFilesystem({ fstype: "fat32" }),
    });
    expect(canBePartitioned(disk)).toBe(false);
  });

  it("handles volume groups", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canBePartitioned(disk)).toBe(false);
  });

  it("handles logical volumes", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      parent: {
        id: 1,
        type: DiskTypes.VOLUME_GROUP,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    expect(canBePartitioned(disk)).toBe(false);
  });

  it("handles bcaches", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      parent: {
        id: 1,
        type: DiskTypes.BCACHE,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    expect(canBePartitioned(disk)).toBe(false);
  });
});

describe("canCreateBcache", () => {
  it("handles machines with cache sets", () => {
    const backingDevice = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.PHYSICAL,
    });
    const noCacheSet = [factory.nodeDisk({ type: DiskTypes.PHYSICAL })];
    const hasCacheSet = [factory.nodeDisk({ type: DiskTypes.CACHE_SET })];
    expect(canCreateBcache(noCacheSet, backingDevice)).toBe(false);
    expect(canCreateBcache(hasCacheSet, backingDevice)).toBe(true);
  });

  it("handles volume groups", () => {
    const volumeGroup = factory.nodeDisk({ type: DiskTypes.VOLUME_GROUP });
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    expect(canCreateBcache([cacheSet], volumeGroup)).toBe(false);
  });

  it("handles bcaches", () => {
    const bcache = factory.nodeDisk({
      name: "bcache0",
      parent: {
        id: 0,
        type: DiskTypes.BCACHE,
        uuid: "bcache0",
      },
      type: DiskTypes.VIRTUAL,
    });
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    expect(canCreateBcache([cacheSet], bcache)).toBe(false);
  });

  it("handles formatted storage devices", () => {
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    const [formattedDisk, unformattedDisk] = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        filesystem: factory.nodeFilesystem(),
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        filesystem: null,
      }),
    ];
    const [formattedPartition, unformattedPartition] = [
      factory.nodePartition({ filesystem: factory.nodeFilesystem() }),
      factory.nodePartition({ filesystem: null }),
    ];
    expect(canCreateBcache([cacheSet], formattedDisk)).toBe(false);
    expect(canCreateBcache([cacheSet], unformattedDisk)).toBe(true);
    expect(canCreateBcache([cacheSet], formattedPartition)).toBe(false);
    expect(canCreateBcache([cacheSet], unformattedPartition)).toBe(true);
  });
});

describe("canCreateCacheSet", () => {
  it("handles null case", () => {
    expect(canCreateCacheSet(null)).toBe(false);
  });

  it("handles disks that have been partitioned", () => {
    const [partitioned, unpartitioned] = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        partitions: [factory.nodePartition(), factory.nodePartition()],
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        partitions: [],
        type: DiskTypes.PHYSICAL,
      }),
    ];
    expect(canCreateCacheSet(partitioned)).toBe(false);
    expect(canCreateCacheSet(unpartitioned)).toBe(true);
  });

  it("handles volume groups", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: [],
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canCreateCacheSet(disk)).toBe(false);
  });

  it("handles formatted storage devices", () => {
    const [formattedDisk, unformattedDisk] = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        filesystem: factory.nodeFilesystem(),
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        filesystem: null,
      }),
    ];
    const [formattedPartition, unformattedPartition] = [
      factory.nodePartition({ filesystem: factory.nodeFilesystem() }),
      factory.nodePartition({ filesystem: null }),
    ];
    expect(canCreateCacheSet(formattedDisk)).toBe(false);
    expect(canCreateCacheSet(unformattedDisk)).toBe(true);
    expect(canCreateCacheSet(formattedPartition)).toBe(false);
    expect(canCreateCacheSet(unformattedPartition)).toBe(true);
  });
});

describe("canCreateLogicalVolume", () => {
  it("handles null case", () => {
    expect(canCreateLogicalVolume(null)).toBe(false);
  });

  it("handles disks that are not volume groups", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.PHYSICAL,
    });
    expect(canCreateLogicalVolume(disk)).toBe(false);
  });

  it("handles mounted volume groups with available space", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      filesystem: factory.nodeFilesystem(),
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canCreateLogicalVolume(disk)).toBe(false);
  });

  it("handles unmounted volume groups with available space", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canCreateLogicalVolume(disk)).toBe(true);
  });
});

describe("canCreateOrUpdateDatastore", () => {
  it("handles an empty array", () => {
    expect(canCreateOrUpdateDatastore([])).toBe(false);
  });

  it("handles volume groups", () => {
    const volumeGroup = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: null,
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canCreateOrUpdateDatastore([volumeGroup])).toBe(false);
  });

  it("handles bcaches", () => {
    const parent = factory.nodeDisk({ type: DiskTypes.BCACHE });
    const bcache = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      parent: {
        id: parent.id,
        type: parent.type,
        uuid: "bcache0",
      },
      partitions: null,
      type: DiskTypes.VIRTUAL,
    });
    expect(canCreateOrUpdateDatastore([bcache])).toBe(false);
  });

  it("handles logical volumes", () => {
    const parent = factory.nodeDisk({ type: DiskTypes.VOLUME_GROUP });
    const logicalVolume = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      parent: {
        id: parent.id,
        type: parent.type,
        uuid: "vg0",
      },
      partitions: null,
      type: DiskTypes.VIRTUAL,
    });
    expect(canCreateOrUpdateDatastore([logicalVolume])).toBe(false);
  });

  it("handles unpartitioned disks", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: null,
      type: DiskTypes.PHYSICAL,
    });
    expect(canCreateOrUpdateDatastore([disk])).toBe(true);
  });

  it("handles unformatted partitions", () => {
    const partition = factory.nodePartition({
      filesystem: null,
    });
    expect(canCreateOrUpdateDatastore([partition])).toBe(true);
  });
});

describe("canCreateRaid", () => {
  it("handles an empty array", () => {
    expect(canCreateRaid([])).toBe(false);
  });

  it("handles arrays with length === 1", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: null,
    });
    expect(canCreateRaid([disk])).toBe(false);
  });

  it("handles unpartitioned disks", () => {
    const disks = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        partitions: null,
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        partitions: null,
        type: DiskTypes.PHYSICAL,
      }),
    ];
    expect(canCreateRaid(disks)).toBe(true);
  });

  it("handles unformatted partitions", () => {
    const partitions = [
      factory.nodePartition({
        filesystem: null,
      }),
      factory.nodePartition({
        filesystem: null,
      }),
    ];
    expect(canCreateRaid(partitions)).toBe(true);
  });

  it("handles formatted filesystems", () => {
    const devices = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        filesystem: factory.nodeFilesystem({ fstype: "ext4", mount_point: "" }),
        partitions: null,
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodePartition({
        filesystem: factory.nodeFilesystem({ fstype: "ext4", mount_point: "" }),
      }),
    ];
    expect(canCreateRaid(devices)).toBe(false);
  });
});

describe("canCreateVolumeGroup", () => {
  it("handles an empty array", () => {
    expect(canCreateVolumeGroup([])).toBe(false);
  });

  it("handles volume groups", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: null,
      type: DiskTypes.VOLUME_GROUP,
    });
    expect(canCreateVolumeGroup([disk])).toBe(false);
  });

  it("handles unpartitioned disks", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      partitions: null,
      type: DiskTypes.PHYSICAL,
    });
    expect(canCreateVolumeGroup([disk])).toBe(true);
  });

  it("handles unformatted partitions", () => {
    const partition = factory.nodePartition({
      filesystem: null,
    });
    expect(canCreateVolumeGroup([partition])).toBe(true);
  });

  it("handles a mix of disks and partitions", () => {
    const devices = [
      factory.nodeDisk({
        available_size: MIN_PARTITION_SIZE + 1,
        partitions: null,
        type: DiskTypes.PHYSICAL,
      }),
      factory.nodePartition({
        filesystem: null,
      }),
    ];
    expect(canCreateVolumeGroup(devices)).toBe(true);
  });
});

describe("canOsSupportBcacheZFS", () => {
  it("handles a machine that supports bcache and ZFS", () => {
    expect(
      canOsSupportBcacheZFS(factory.machineDetails({ osystem: "ubuntu" }))
    ).toBe(true);
  });

  it("handles a machine that does not support bcache and ZFS", () => {
    expect(
      canOsSupportBcacheZFS(factory.machineDetails({ osystem: "centos" }))
    ).toBe(false);
  });
});

describe("canOsSupportStorageConfig", () => {
  it("handles a machine that supports configurating storage layout", () => {
    expect(
      canOsSupportStorageConfig(factory.machineDetails({ osystem: "ubuntu" }))
    ).toBe(true);
  });

  it("handles a machine that does not support configurating storage layout", () => {
    expect(
      canOsSupportStorageConfig(factory.machineDetails({ osystem: "windows" }))
    ).toBe(false);
  });
});

describe("canSetBootDisk", () => {
  it("handles vmfs6 storage layout", () => {
    const disk = factory.nodeDisk({ is_boot: false, type: DiskTypes.PHYSICAL });
    expect(canSetBootDisk(StorageLayout.VMFS6, disk)).toBe(false);
    expect(canSetBootDisk(StorageLayout.BLANK, disk)).toBe(true);
  });

  it("handles non-physical disks", () => {
    const physicalDisk = factory.nodeDisk({
      is_boot: false,
      type: DiskTypes.PHYSICAL,
    });
    const nonPhysicalDisk = factory.nodeDisk({
      is_boot: false,
      type: DiskTypes.VIRTUAL,
    });
    expect(canSetBootDisk(StorageLayout.BLANK, nonPhysicalDisk)).toBe(false);
    expect(canSetBootDisk(StorageLayout.BLANK, physicalDisk)).toBe(true);
  });

  it("handles boot disks", () => {
    const bootDisk = factory.nodeDisk({
      is_boot: true,
      type: DiskTypes.PHYSICAL,
    });
    const nonBootDisk = factory.nodeDisk({
      is_boot: false,
      type: DiskTypes.PHYSICAL,
    });
    expect(canSetBootDisk(StorageLayout.BLANK, bootDisk)).toBe(false);
    expect(canSetBootDisk(StorageLayout.BLANK, nonBootDisk)).toBe(true);
  });
});

describe("diskAvailable", () => {
  it("handles null case", () => {
    expect(diskAvailable(null)).toBe(false);
  });

  it("handles disks with available space", () => {
    const disk = factory.nodeDisk({
      available_size: MIN_PARTITION_SIZE + 1,
      type: DiskTypes.PHYSICAL,
    });
    expect(diskAvailable(disk)).toBe(true);
  });

  it("handles cache sets", () => {
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    expect(diskAvailable(cacheSet)).toBe(false);
  });

  it("handles unmounted RAIDs", () => {
    const raid0 = factory.nodeDisk({
      available_size: 0,
      filesystem: null,
      type: DiskTypes.RAID_0,
    });
    expect(diskAvailable(raid0)).toBe(false);
  });

  it("handles mounted disks", () => {
    const mounted = factory.nodeDisk({
      filesystem: factory.nodeFilesystem({ mount_point: "/path" }),
    });
    expect(diskAvailable(mounted)).toBe(false);
  });
});

describe("formatSize", () => {
  it("handles null case", () => {
    expect(formatSize(null)).toBe("—");
    expect(formatSize(0)).toBe("—");
  });

  it("can format size", () => {
    expect(formatSize(100)).toBe("100 B");
    expect(formatSize(10000)).toBe("10 KB");
  });
});

describe("formatType", () => {
  it("handles null case", () => {
    expect(formatType(null)).toBe("Unknown");
  });

  it("handles cache sets", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    expect(formatType(disk)).toBe("Cache set");
    expect(formatType(disk, true)).toBe("cache set");
  });

  it("handles ISCSIs", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.ISCSI });
    expect(formatType(disk)).toBe("ISCSI");
  });

  it("handles logical volumes", () => {
    const disk = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.VOLUME_GROUP,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    expect(formatType(disk)).toBe("Logical volume");
    expect(formatType(disk, true)).toBe("logical volume");
  });

  it("handles partitions", () => {
    const partition = factory.nodePartition({ type: "partition" });
    expect(formatType(partition)).toBe("Partition");
    expect(formatType(partition, true)).toBe("partition");
  });

  it("handles physical disks", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(formatType(disk)).toBe("Physical");
    expect(formatType(disk, true)).toBe("physical disk");
  });

  it("handles RAIDs", () => {
    const disk = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.RAID_0,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    expect(formatType(disk)).toBe("RAID 0");
  });

  it("handles VMFS6 datastores", () => {
    const partition = factory.nodePartition({ type: "vmfs6" });
    expect(formatType(partition)).toBe("VMFS6");
  });

  it("handles virtual disks", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.VIRTUAL });
    expect(formatType(disk)).toBe("Virtual");
    expect(formatType(disk, true)).toBe("virtual disk");
  });

  it("handles volume groups", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.VOLUME_GROUP });
    expect(formatType(disk)).toBe("Volume group");
    expect(formatType(disk, true)).toBe("volume group");
  });
});

describe("getDiskById", () => {
  it("returns a machine's disk given the disk's id", () => {
    const disk1 = factory.nodeDisk({ id: 1 });
    const disk2 = factory.nodeDisk({
      id: 2,
      partitions: [factory.nodePartition({ id: 1 })],
    });
    expect(getDiskById([disk1, disk2], 1)).toBe(disk1);
    expect(getDiskById([disk1, disk2], 2)).toBe(disk2);
    expect(getDiskById([disk1, disk2], 3)).toBe(null);
  });
});

describe("getPartitionById", () => {
  it("returns a machine's disk partition given the partition's id", () => {
    const partition1 = factory.nodePartition({ id: 1 });
    const partition2 = factory.nodePartition({ id: 2 });
    const disks = [
      factory.nodeDisk({ id: 1, partitions: [partition1] }),
      factory.nodeDisk({ id: 2, partitions: [partition2] }),
    ];
    expect(getPartitionById(disks, 1)).toBe(partition1);
    expect(getPartitionById(disks, 2)).toBe(partition2);
    expect(getPartitionById(disks, 3)).toBe(null);
  });
});

describe("isBcache", () => {
  it("returns whether a disk is a bcache", () => {
    const bcache = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.BCACHE,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    const notBcache = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isBcache(null)).toBe(false);
    expect(isBcache(notBcache)).toBe(false);
    expect(isBcache(bcache)).toBe(true);
  });
});

describe("isCacheSet", () => {
  it("returns whether a disk is a cache set", () => {
    const cacheSet = factory.nodeDisk({ type: DiskTypes.CACHE_SET });
    const notCacheSet = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isCacheSet(null)).toBe(false);
    expect(isCacheSet(notCacheSet)).toBe(false);
    expect(isCacheSet(cacheSet)).toBe(true);
  });
});

describe("isDatastore", () => {
  it("returns whether a filesystem is a datastore", () => {
    const datastore = factory.nodeFilesystem({ fstype: "vmfs6" });
    const notDatastore = factory.nodeFilesystem({ fstype: "fat32" });
    expect(isDatastore(null)).toBe(false);
    expect(isDatastore(notDatastore)).toBe(false);
    expect(isDatastore(datastore)).toBe(true);
  });
});

describe("isDisk", () => {
  it("returns whether a storage device is a disk", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    const partition = factory.nodePartition({ type: "partition" });
    expect(isDisk(null)).toBe(false);
    expect(isDisk(partition)).toBe(false);
    expect(isDisk(disk)).toBe(true);
  });
});

describe("isFormatted", () => {
  it("returns whether a filesystem has been formatted", () => {
    const formatted = factory.nodeFilesystem({ fstype: "vmfs6" });
    const unformatted = factory.nodeFilesystem({ fstype: "" });
    expect(isFormatted(null)).toBe(false);
    expect(isFormatted(unformatted)).toBe(false);
    expect(isFormatted(formatted)).toBe(true);
  });
});

describe("isLogicalVolume", () => {
  it("returns whether a disk is a logical volume", () => {
    const logicalVolume = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.VOLUME_GROUP,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    const notLogicalVolume = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isLogicalVolume(null)).toBe(false);
    expect(isLogicalVolume(notLogicalVolume)).toBe(false);
    expect(isLogicalVolume(logicalVolume)).toBe(true);
  });
});

describe("isNodeStorageConfigurable", () => {
  it("handles a machine in a configurable state", () => {
    expect(
      isNodeStorageConfigurable(
        factory.machineDetails({ status_code: NodeStatusCode.READY })
      )
    ).toBe(true);
  });

  it("handles a machine in a non-configurable state", () => {
    expect(
      isNodeStorageConfigurable(
        factory.machineDetails({ status_code: NodeStatusCode.ALLOCATED })
      )
    ).toBe(false);
    expect(
      isNodeStorageConfigurable(
        factory.machineDetails({ status_code: NodeStatusCode.NEW })
      )
    ).toBe(false);
  });

  it("handles a controller", () => {
    expect(
      isNodeStorageConfigurable(
        factory.controller({ status_code: NodeStatusCode.READY })
      )
    ).toBe(false);
  });
});

describe("isMounted", () => {
  it("returns whether a filesystem is mounted", () => {
    const mounted = factory.nodeFilesystem({ mount_point: "/" });
    const notMounted = factory.nodeFilesystem({ mount_point: "" });
    expect(isMounted(null)).toBe(false);
    expect(isMounted(notMounted)).toBe(false);
    expect(isMounted(mounted)).toBe(true);
  });

  it("handles reserved filesystems", () => {
    const reserved = factory.nodeFilesystem({ mount_point: "RESERVED" });
    expect(isMounted(reserved)).toBe(false);
  });
});

describe("isPartition", () => {
  it("returns whether a storage device is a partition", () => {
    const disk = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    const partition = factory.nodePartition({ type: "partition" });
    expect(isPartition(null)).toBe(false);
    expect(isPartition(disk)).toBe(false);
    expect(isPartition(partition)).toBe(true);
  });
});

describe("isRaid", () => {
  it("returns whether a disk is a RAID", () => {
    const raid = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.RAID_0,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    const notRaid = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isRaid(null)).toBe(false);
    expect(isRaid(notRaid)).toBe(false);
    expect(isRaid(raid)).toBe(true);
  });
});

describe("isPhysical", () => {
  it("returns whether a disk is a physical disk", () => {
    const physical = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    const notPhysical = factory.nodeDisk({ type: DiskTypes.VIRTUAL });
    expect(isPhysical(null)).toBe(false);
    expect(isPhysical(notPhysical)).toBe(false);
    expect(isPhysical(physical)).toBe(true);
  });
});

describe("isVirtual", () => {
  it("returns whether a disk is a virtual disk", () => {
    const virtual = factory.nodeDisk({
      parent: {
        id: 1,
        type: DiskTypes.RAID_0,
        uuid: "abc123",
      },
      type: DiskTypes.VIRTUAL,
    });
    const notVirtual = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isVirtual(null)).toBe(false);
    expect(isVirtual(notVirtual)).toBe(false);
    expect(isVirtual(virtual)).toBe(true);
  });
});

describe("isVMWareLayout", () => {
  it("returns whether a storage layout is used for VMWare ESXi", () => {
    expect(isVMWareLayout(StorageLayout.VMFS6)).toBe(true);
    expect(isVMWareLayout(StorageLayout.VMFS7)).toBe(true);
    expect(isVMWareLayout(StorageLayout.BLANK)).toBe(false);
  });
});

describe("isVolumeGroup", () => {
  it("returns whether a disk is a volume group", () => {
    const vg = factory.nodeDisk({
      type: DiskTypes.VOLUME_GROUP,
    });
    const notVg = factory.nodeDisk({ type: DiskTypes.PHYSICAL });
    expect(isVolumeGroup(null)).toBe(false);
    expect(isVolumeGroup(notVg)).toBe(false);
    expect(isVolumeGroup(vg)).toBe(true);
  });
});

describe("partitionAvailable", () => {
  it("handles null case", () => {
    expect(partitionAvailable(null)).toBe(false);
  });

  it("handles mounted partitions", () => {
    const partition = factory.nodePartition({
      filesystem: factory.nodeFilesystem({ mount_point: "/path" }),
    });
    expect(partitionAvailable(partition)).toBe(false);
  });

  it("handles unmounted partitions that can be formatted", () => {
    const partition = factory.nodePartition({
      filesystem: factory.nodeFilesystem({
        is_format_fstype: true,
        mount_point: "",
      }),
    });
    expect(partitionAvailable(partition)).toBe(true);
  });
});

describe("splitDiskPartitionIds", () => {
  it("handles empty array case", () => {
    expect(splitDiskPartitionIds([])).toStrictEqual([[], []]);
  });

  it("can split a list of storage devices into disk ids and partition ids", () => {
    const disks = [factory.nodeDisk(), factory.nodeDisk()];
    const partitions = [factory.nodePartition(), factory.nodePartition()];
    const combined = [...disks, ...partitions];
    expect(splitDiskPartitionIds(combined)).toStrictEqual([
      [disks[0].id, disks[1].id],
      [partitions[0].id, partitions[1].id],
    ]);
  });
});

describe("usesStorage", () => {
  it("handles null case", () => {
    expect(usesStorage(null)).toBe(false);
  });

  it("returns whether a filesystem type uses storage", () => {
    const fs1 = "fat32";
    const fs2 = "ramfs";
    const fs3 = "tmpfs";
    expect(usesStorage(fs1)).toBe(true);
    expect(usesStorage(fs2)).toBe(false);
    expect(usesStorage(fs3)).toBe(false);
  });
});

describe("getNextStorageName", () => {
  describe("volume group", () => {
    it("can get the next name", () => {
      const disks = [
        factory.nodeDisk({ name: "vg0", type: DiskTypes.VOLUME_GROUP }),
      ];
      expect(getNextStorageName(disks, "vg")).toStrictEqual("vg1");
    });

    it("can get the next name when there are no existing items", () => {
      expect(getNextStorageName([], "vg")).toStrictEqual("vg0");
    });

    it("can get the next name when the names are out of order", () => {
      const disks = [
        factory.nodeDisk({ name: "vg1", type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ name: "vg2", type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ name: "vg0", type: DiskTypes.VOLUME_GROUP }),
      ];
      expect(getNextStorageName(disks, "vg")).toStrictEqual("vg3");
    });

    it("can get the name when there are non sequential names", () => {
      const disks = [
        factory.nodeDisk({ name: "vg0", type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ name: "vg2", type: DiskTypes.VOLUME_GROUP }),
      ];
      expect(getNextStorageName(disks, "vg")).toStrictEqual("vg3");
    });

    it("can get the next name when there are partial names", () => {
      const disks = [
        factory.nodeDisk({ name: "vg0", type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ name: "vg", type: DiskTypes.VOLUME_GROUP }),
      ];
      expect(getNextStorageName(disks, "vg")).toStrictEqual("vg1");
    });

    it("can get the next name when there are partial similar names", () => {
      const disks = [
        factory.nodeDisk({ name: "vg0", type: DiskTypes.VOLUME_GROUP }),
        factory.nodeDisk({ name: "vg2vg1", type: DiskTypes.VOLUME_GROUP }),
      ];
      expect(getNextStorageName(disks, "vg")).toStrictEqual("vg1");
    });
  });

  describe("raid", () => {
    it("can get the next name", () => {
      const disks = [
        factory.nodeDisk({
          name: "md0",
          parent: {
            id: 1,
            type: DiskTypes.RAID_0,
            uuid: "abc123",
          },
          type: DiskTypes.VIRTUAL,
        }),
      ];
      expect(getNextStorageName(disks, "md")).toStrictEqual("md1");
    });

    it("can get the next name when there are no existing items", () => {
      expect(getNextStorageName([], "md")).toStrictEqual("md0");
    });
  });

  describe("bcache", () => {
    it("can get the next name", () => {
      const disks = [
        factory.nodeDisk({
          name: "bcache0",
          parent: {
            id: 1,
            type: DiskTypes.BCACHE,
            uuid: "abc123",
          },
          type: DiskTypes.VIRTUAL,
        }),
      ];
      expect(getNextStorageName(disks, "bcache")).toStrictEqual("bcache1");
    });

    it("can get the next name when there are no existing items", () => {
      expect(getNextStorageName([], "bcache")).toStrictEqual("bcache0");
    });
  });

  describe("datastore", () => {
    it("can get the next name", () => {
      const disks = [
        factory.nodeDisk({
          filesystem: factory.nodeFilesystem({ fstype: "vmfs6" }),
          name: "datastore1",
        }),
      ];
      expect(getNextStorageName(disks, "datastore")).toStrictEqual(
        "datastore2"
      );
    });

    it("can get the next name when there are no existing items", () => {
      expect(getNextStorageName([], "datastore")).toStrictEqual("datastore1");
    });
  });
});
