import type { ReactNode } from "react";

import type { ValueOf } from "@canonical/react-components";
import type { MainTableCell } from "@canonical/react-components/dist/components/MainTable/MainTable";

import type { SortDirection } from "@/app/base/types";
import type { MachineColumns } from "@/app/machines/constants";
import type { GetMachineMenuToggleHandler } from "@/app/machines/types";
import type {
  Machine,
  MachineStateListGroup,
  FetchGroupKey,
  FetchFilters,
} from "@/app/store/machine/types";
import type { useFetchMachines } from "@/app/store/machine/utils/hooks";

export type MachineListTableProps = {
  callId?: string | null;
  currentPage: number;
  filter?: string;
  grouping?: FetchGroupKey | null;
  groups: MachineStateListGroup[] | null;
  hiddenColumns?: string[];
  hiddenGroups?: (string | null)[];
  machineCount: number | null;
  machines: Machine[];
  machinesLoading?: boolean | null;
  pageSize: number;
  totalPages: ReturnType<typeof useFetchMachines>["totalPages"];
  setCurrentPage: (currentPage: number) => void;
  setHiddenGroups?: (hiddenGroups: (string | null)[]) => void;
  setPageSize?: (pageSize: number) => void;
  showActions?: boolean;
  sortDirection: ValueOf<typeof SortDirection>;
  sortKey: FetchGroupKey | null;
  setSortDirection: (sortDirection: ValueOf<typeof SortDirection>) => void;
  setSortKey: (sortKey: FetchGroupKey | null) => void;
};

export type GroupRowsProps = Omit<GenerateRowParams, "groupValue"> & {
  callId?: string | null;
  grouping?: FetchGroupKey | null;
  groups: MachineStateListGroup[] | null;
  hiddenGroups: NonNullable<MachineListTableProps["hiddenGroups"]>;
  setHiddenGroups: MachineListTableProps["setHiddenGroups"];
  filter: FetchFilters | null;
};

export type TableColumn = MainTableCell & { key: string };

export type GenerateRowParams = {
  callId?: string | null;
  groupValue: MachineStateListGroup["value"];
  hiddenColumns: NonNullable<MachineListTableProps["hiddenColumns"]>;
  machines: Machine[];
  getToggleHandler: GetMachineMenuToggleHandler;
  showActions: MachineListTableProps["showActions"];
  showMAC: boolean;
  showFullName: boolean;
};

export type RowContent = {
  [MachineColumns.FQDN]: ReactNode;
  [MachineColumns.POWER]: ReactNode;
  [MachineColumns.STATUS]: ReactNode;
  [MachineColumns.OWNER]: ReactNode;
  [MachineColumns.POOL]: ReactNode;
  [MachineColumns.ZONE]: ReactNode;
  [MachineColumns.FABRIC]: ReactNode;
  [MachineColumns.CPU]: ReactNode;
  [MachineColumns.MEMORY]: ReactNode;
  [MachineColumns.DISKS]: ReactNode;
  [MachineColumns.STORAGE]: ReactNode;
};
