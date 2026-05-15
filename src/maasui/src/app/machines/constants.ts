import { FetchGroupKey } from "@/app/store/machine/types";

export const columns = [
  "fqdn",
  "power",
  "status",
  "owner",
  "pool",
  "zone",
  "fabric",
  "cpu",
  "memory",
  "disks",
  "storage",
] as const;
export type MachineColumn = (typeof columns)[number];
export type MachineColumnToggle = Exclude<MachineColumn, "fqdn">;
function isMachineColumnToggle(
  column: MachineColumn
): column is MachineColumnToggle {
  return column !== "fqdn";
}
export const columnToggles = columns.filter(isMachineColumnToggle);

export enum MachineColumns {
  FQDN = "fqdn",
  POWER = "power",
  STATUS = "status",
  OWNER = "owner",
  POOL = "pool",
  ZONE = "zone",
  FABRIC = "fabric",
  CPU = "cpu",
  MEMORY = "memory",
  DISKS = "disks",
  STORAGE = "storage",
}

export const columnLabels: Record<MachineColumns, string> = {
  fqdn: "FQDN",
  power: "Power",
  status: "Status",
  owner: "Owner",
  pool: "Pool",
  zone: "Zone",
  fabric: "Fabric",
  cpu: "Cores",
  memory: "RAM",
  disks: "Disks",
  storage: "Storage",
};

export const groupOptions: { value: FetchGroupKey | ""; label: string }[] = [
  {
    value: "",
    label: "No grouping",
  },
  {
    value: FetchGroupKey.Status,
    label: "Group by status",
  },
  {
    value: FetchGroupKey.Owner,
    label: "Group by owner",
  },
  {
    value: FetchGroupKey.Pool,
    label: "Group by resource pool",
  },
  {
    value: FetchGroupKey.Architecture,
    label: "Group by architecture",
  },
  {
    value: FetchGroupKey.Domain,
    label: "Group by domain",
  },
  {
    value: FetchGroupKey.Parent,
    label: "Group by parent",
  },
  {
    value: FetchGroupKey.Pod,
    label: "Group by KVM",
  },
  {
    value: FetchGroupKey.PodType,
    label: "Group by KVM type",
  },
  {
    value: FetchGroupKey.PowerState,
    label: "Group by power state",
  },
  {
    value: FetchGroupKey.Zone,
    label: "Group by zone",
  },
];
