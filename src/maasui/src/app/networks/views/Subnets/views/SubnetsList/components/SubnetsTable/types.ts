import type { ReactNode } from "react";

import type { SubnetsColumns } from "./constants";

import type { Fabric } from "@/app/store/fabric/types";
import type { Space } from "@/app/store/space/types";
import type { Subnet } from "@/app/store/subnet/types";
import type { VLAN } from "@/app/store/vlan/types";

export type GroupByKey = "fabric" | "space";

export type SubnetsTableData = {
  fabrics: Fabric[];
  vlans: VLAN[];
  subnets: Subnet[];
  spaces: Space[];
};

export type SubnetsTableColumn = {
  isVisuallyHidden: boolean;
  label: string | null;
  href: string | null;
};

type SortKey = number | string;

export type SortData = {
  fabricId: SortKey;
  fabricName: SortKey;
  vlanId: SortKey;
  spaceName: SortKey;
  cidr: SortKey;
};

export type FabricTableRow = {
  fabricId: SortKey;
  fabricName: SortKey;
  isCollapsed: boolean;
  networks: SubnetsTableRow[];
};

export type SpaceTableRow = {
  spaceName: SortKey;
  isCollapsed: boolean;
  networks: SubnetsTableRow[];
};

export type SubnetGroupByProps = {
  groupBy: GroupByKey;
  setGroupBy: (group: GroupByKey) => void;
};

export type SortDataKey =
  | "cidr"
  | "fabricId"
  | "fabricName"
  | "spaceName"
  | "vlanId";

export type SubnetsTableRow = Record<SubnetsColumns, SubnetsTableColumn> & {
  sortData: SortData;
  "aria-label"?: string;
};

export type FabricRowContent = {
  [SubnetsColumns.FABRIC]: ReactNode;
  [SubnetsColumns.VLAN]: ReactNode;
  [SubnetsColumns.DHCP]: ReactNode;
  [SubnetsColumns.SUBNET]: ReactNode;
  [SubnetsColumns.IPS]: ReactNode;
  [SubnetsColumns.SPACE]: ReactNode;
};
