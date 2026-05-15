import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import { LicenseKeyEdit } from "@/app/settings/views/LicenseKeys/components";
import LicenseKeyDelete from "@/app/settings/views/LicenseKeys/components/LicenseKeyDelete/LicenseKeyDelete";
import type { LicenseKeys } from "@/app/store/licensekeys/types";

type LicenseKeysColumnDef = ColumnDef<LicenseKeys, Partial<LicenseKeys>>;

const useLicenseKeyTableColumns = (): LicenseKeysColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo(
    () => [
      {
        id: "osystem",
        accessorKey: "osystem",
        enableSorting: true,
        header: "Operating System",
      },
      {
        id: "distro_series",
        accessorKey: "distro_series",
        enableSorting: true,
        header: "Distro Series",
      },
      {
        id: "actions",
        accessorKey: "license_key",
        header: "Actions",
        cell: ({ row: { original } }) => (
          <TableActions
            onDelete={() => {
              openSidePanel({
                component: LicenseKeyDelete,
                title: "Delete license key",
                props: {
                  licenseKey: original,
                },
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: LicenseKeyEdit,
                title: "Edit license key",
                props: {
                  osystem: original.osystem,
                  distro_series: original.distro_series,
                },
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useLicenseKeyTableColumns;
