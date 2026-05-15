import { useMemo } from "react";

import type { ColumnDef } from "@tanstack/react-table";

import APIKeyDelete from "../../APIKeyDelete";
import APIKeyEdit from "../../APIKeyEdit";

import TableActions from "@/app/base/components/TableActions";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { Token } from "@/app/store/token/types";

export type TokenRowData = {
  id: Token["id"];
  name: Token["consumer"]["name"];
  key: string;
};

type APIKeyColumnDef = ColumnDef<TokenRowData, Partial<TokenRowData>>;

export const formatToken = (
  consumerKey: Token["consumer"]["key"],
  key: Token["key"],
  secret: Token["secret"]
): string => `${consumerKey}:${key}:${secret}`;

const useAPIKeyTableColumns = (): APIKeyColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo(
    (): APIKeyColumnDef[] => [
      {
        id: "name",
        accessorKey: "name",
        header: "Name",
        enableSorting: true,
      },
      {
        id: "key",
        accessorKey: "key",
        header: "Key",
        enableSorting: false,
      },
      {
        id: "actions",
        accessorKey: "id",
        header: "Actions",
        enableSorting: false,
        cell: ({
          row: {
            original: { id, key },
          },
        }) => (
          <TableActions
            copyValue={key}
            onDelete={() => {
              openSidePanel({
                component: APIKeyDelete,
                props: { id },
                title: "Delete API key",
              });
            }}
            onEdit={() => {
              openSidePanel({
                component: APIKeyEdit,
                props: { id },
                title: "Edit API key",
              });
            }}
          />
        ),
      },
    ],
    [openSidePanel]
  );
};

export default useAPIKeyTableColumns;
