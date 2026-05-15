import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import RowCheckbox from "@/app/base/components/RowCheckbox";
import type { KnownBootArchitecture } from "@/app/store/general/types";

export type BootArchesRow = KnownBootArchitecture & { id: number };

export type BootArchitecturesColumnDef = ColumnDef<
  BootArchesRow,
  Partial<BootArchesRow>
>;

export type UseBootArchicturesColumnsProps = {
  isChecked: (item: string, rows: string[]) => boolean;
  handleArchChange: (bootArchName: string) => void;
  disabledBootArches: string[];
};

const useBootArchitecturesColumns = ({
  isChecked,
  handleArchChange,
  disabledBootArches,
}: UseBootArchicturesColumnsProps): BootArchitecturesColumnDef[] => {
  return useMemo(
    (): BootArchitecturesColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        cell: ({
          row: {
            original: { name },
          },
        }) => (
          <RowCheckbox
            checkSelected={isChecked}
            handleRowCheckbox={handleArchChange}
            inputLabel={name}
            item={name}
            items={disabledBootArches}
          />
        ),
      },
      {
        id: "bios_boot_method",
        accessorKey: "bios_boot_method",
        header: "BIOS boot method",
      },
      {
        id: "bootloader_arches",
        accessorKey: "bootloader_arches",
        header: "Bootloader architecture",
        cell: ({ row }) => row.original.bootloader_arches || "—",
      },
      {
        id: "protocol",
        accessorKey: "protocol",
      },
      {
        id: "arch_octet",
        accessorKey: "arch_octet",
        header: "Architecture octet",
        cell: ({ row }) => row.original.arch_octet || "—",
      },
    ],
    [disabledBootArches, handleArchChange, isChecked]
  );
};

export default useBootArchitecturesColumns;
