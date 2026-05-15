import { NodeActions } from "../types/node";

import type { Action } from "./types";

import { DiskTypes } from "@/app/store/types/enum";

// From models/partition.py. This should ideally be available over the websocket.
// https://github.com/canonical/maas-ui/issues/1866
export const MIN_PARTITION_SIZE = 4 * 1024 * 1024;

export type RaidMode = {
  allowsSpares: boolean;
  calculateSize: (minSize: number, numActive: number) => number;
  label: string;
  level:
    | DiskTypes.RAID_0
    | DiskTypes.RAID_1
    | DiskTypes.RAID_5
    | DiskTypes.RAID_6
    | DiskTypes.RAID_10;
  minDevices: number;
};
// This should be made available over the websocket.
// https://github.com/canonical/maas-ui/issues/1866
export const RAID_MODES: RaidMode[] = [
  {
    allowsSpares: false,
    calculateSize: (minSize: number, numActive: number): number =>
      minSize * numActive,
    label: "RAID 0",
    level: DiskTypes.RAID_0,
    minDevices: 2,
  },
  {
    allowsSpares: true,
    calculateSize: (minSize: number, _: number): number => minSize,
    label: "RAID 1",
    level: DiskTypes.RAID_1,
    minDevices: 2,
  },
  {
    allowsSpares: true,
    calculateSize: (minSize: number, numActive: number): number =>
      minSize * (numActive - 1),
    label: "RAID 5",
    level: DiskTypes.RAID_5,
    minDevices: 3,
  },
  {
    allowsSpares: true,
    calculateSize: (minSize: number, numActive: number): number =>
      minSize * (numActive - 2),
    label: "RAID 6",
    level: DiskTypes.RAID_6,
    minDevices: 4,
  },
  {
    allowsSpares: true,
    calculateSize: (minSize: number, numActive: number): number =>
      (minSize * numActive) / 2,
    label: "RAID 10",
    level: DiskTypes.RAID_10,
    minDevices: 3,
  },
];

export const ACTIONS: Action[] = [
  {
    name: NodeActions.ABORT,
    status: "aborting",
  },
  {
    name: NodeActions.ACQUIRE,
    status: "acquiring",
  },
  {
    name: "apply-storage-layout",
    status: "applyingStorageLayout",
  },
  {
    name: "check-power",
    status: "checkingPower",
  },
  {
    name: NodeActions.CLONE,
    status: "cloning",
  },
  {
    name: NodeActions.COMMISSION,
    status: "commissioning",
  },
  {
    name: "create-bcache",
    status: "creatingBcache",
  },
  {
    name: "create-bond",
    status: "creatingBond",
  },
  {
    name: "create-bridge",
    status: "creatingBridge",
  },
  {
    name: "create-cache-set",
    status: "creatingCacheSet",
  },
  {
    name: "create-logical-volume",
    status: "creatingLogicalVolume",
  },
  {
    name: "create-partition",
    status: "creatingPartition",
  },
  {
    name: "create-physical",
    status: "creatingPhysical",
  },
  {
    name: "create-raid",
    status: "creatingRaid",
  },
  {
    name: "create-vlan",
    status: "creatingVlan",
  },
  {
    name: "create-vmfs-datastore",
    status: "creatingVmfsDatastore",
  },
  {
    name: "create-volume-group",
    status: "creatingVolumeGroup",
  },
  {
    name: NodeActions.DELETE,
    status: "deleting",
  },
  {
    name: "delete-cache-set",
    status: "deletingCacheSet",
  },
  {
    name: "delete-disk",
    status: "deletingDisk",
  },
  {
    name: "delete-filesystem",
    status: "deletingFilesystem",
  },
  {
    name: "delete-interface",
    status: "deletingInterface",
  },
  {
    name: "delete-partition",
    status: "deletingPartition",
  },
  {
    name: "delete-volume-group",
    status: "deletingVolumeGroup",
  },
  {
    name: NodeActions.DEPLOY,
    status: "deploying",
  },
  {
    name: NodeActions.RESCUE_MODE,
    status: "enteringRescueMode",
  },
  {
    name: NodeActions.EXIT_RESCUE_MODE,
    status: "exitingRescueMode",
  },
  {
    name: "get-summary-xml",
    status: "gettingSummaryXml",
  },
  {
    name: "get-summary-yaml",
    status: "gettingSummaryYaml",
  },
  {
    name: "link-subnet",
    status: "linkingSubnet",
  },
  {
    name: NodeActions.LOCK,
    status: "locking",
  },
  {
    name: NodeActions.MARK_BROKEN,
    status: "markingBroken",
  },
  {
    name: NodeActions.MARK_FIXED,
    status: "markingFixed",
  },
  {
    name: "mount-special",
    status: "mountingSpecial",
  },
  {
    name: NodeActions.OVERRIDE_FAILED_TESTING,
    status: "overridingFailedTesting",
  },
  {
    name: NodeActions.RELEASE,
    status: "releasing",
  },
  {
    name: "set-boot-disk",
    status: "settingBootDisk",
  },
  {
    name: NodeActions.SET_POOL,
    status: "settingPool",
  },
  {
    name: NodeActions.SET_ZONE,
    status: "settingZone",
  },
  {
    name: NodeActions.TAG,
    status: "tagging",
  },
  {
    name: NodeActions.TEST,
    status: "testing",
  },
  {
    name: NodeActions.OFF,
    status: "turningOff",
  },
  {
    name: NodeActions.ON,
    status: "turningOn",
  },
  {
    name: NodeActions.SOFT_OFF,
    status: "turningOff",
  },
  {
    name: NodeActions.UNLOCK,
    status: "unlocking",
  },
  {
    name: "unlink-subnet",
    status: "unlinkingSubnet",
  },
  {
    name: "unmount-special",
    status: "unmountingSpecial",
  },
  {
    name: NodeActions.UNTAG,
    status: "untagging",
  },
  {
    name: "update-disk",
    status: "updatingDisk",
  },
  {
    name: "update-filesystem",
    status: "updatingFilesystem",
  },
  {
    name: "update-interface",
    status: "updatingInterface",
  },
  {
    name: "update-vmfs-datastore",
    status: "updatingVmfsDatastore",
  },
];

export const DEFAULT_STATUSES = {
  aborting: false,
  acquiring: false,
  applyingStorageLayout: false,
  checkingPower: false,
  cloning: false,
  creatingBcache: false,
  creatingBond: false,
  creatingBridge: false,
  creatingCacheSet: false,
  creatingLogicalVolume: false,
  creatingPartition: false,
  creatingPhysical: false,
  creatingRaid: false,
  creatingVlan: false,
  creatingVmfsDatastore: false,
  creatingVolumeGroup: false,
  commissioning: false,
  deleting: false,
  deletingCacheSet: false,
  deletingDisk: false,
  deletingFilesystem: false,
  deletingInterface: false,
  deletingPartition: false,
  deletingVolumeGroup: false,
  deploying: false,
  enteringRescueMode: false,
  exitingRescueMode: false,
  gettingSummaryXml: false,
  gettingSummaryYaml: false,
  linkingSubnet: false,
  locking: false,
  markingBroken: false,
  markingFixed: false,
  mountingSpecial: false,
  overridingFailedTesting: false,
  releasing: false,
  settingBootDisk: false,
  settingPool: false,
  settingZone: false,
  tagging: false,
  testing: false,
  turningOff: false,
  turningOn: false,
  unlocking: false,
  unlinkingSubnet: false,
  unmountingSpecial: false,
  unsubscribing: false,
  untagging: false,
  updatingDisk: false,
  updatingFilesystem: false,
  updatingInterface: false,
  updatingVmfsDatastore: false,
};
