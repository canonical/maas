import type { Dispatch, ReactElement, SetStateAction } from "react";

import { ContextualMenu } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";

import { useGetPool } from "@/app/api/query/pools";
import type {
  EntitlementResponse,
  OpenFgaEntitlementResourceType,
  UserGroupResponse,
} from "@/app/apiclient";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/pools/urls";
import RemoveGroupEntitlement from "@/app/settings/views/UserManagement/views/Groups/components/RemoveGroupEntitlement";

export type EntitlementColumnDef = ColumnDef<
  EntitlementResponse & { id: string },
  Partial<EntitlementResponse & { id: string }>
>;

const AppliesToCell = ({
  id,
  type,
}: {
  id: number;
  type: OpenFgaEntitlementResourceType;
}): ReactElement => {
  const { data: pool } = useGetPool({ path: { resource_pool_id: id } });

  return type === "maas" ? (
    <>MAAS (global)</>
  ) : (
    <Link to={urls.index}>{pool?.name}</Link>
  );
};

const useGroupEntitlementsTableColumns = ({
  group_id,
  setEntitlementSelection,
}: {
  group_id: UserGroupResponse["id"];
  setEntitlementSelection: Dispatch<SetStateAction<EntitlementResponse[]>>;
}): EntitlementColumnDef[] => {
  const { openSidePanel } = useSidePanel();
  return [
    {
      id: "entitlement",
      accessorKey: "entitlement",
      enableSorting: true,
    },
    {
      id: "resource_id",
      accessorKey: "resource_type",
      enableSorting: true,
      header: "Applies to",
      cell: ({
        row: {
          original: { resource_id, resource_type },
        },
      }) => (
        <AppliesToCell
          id={resource_id}
          type={resource_type as OpenFgaEntitlementResourceType}
        />
      ),
    },
    {
      id: "actions",
      accessorKey: "actions",
      enableSorting: false,
      cell: ({
        row: {
          original: { entitlement, resource_id, resource_type },
        },
      }) => (
        <ContextualMenu
          hasToggleIcon
          links={[
            {
              children: "Remove entitlement...",
              onClick: () => {
                openSidePanel({
                  component: RemoveGroupEntitlement,
                  title: "Remove entitlement",
                  props: {
                    group_id,
                    entitlements: [
                      {
                        entitlement,
                        resource_id,
                        resource_type:
                          resource_type as OpenFgaEntitlementResourceType,
                      },
                    ],
                    setEntitlementSelection,
                  },
                });
              },
            },
          ]}
          toggleAppearance="base"
          toggleClassName="u-no-margin--bottom is-small is-dense"
        />
      ),
    },
  ] as EntitlementColumnDef[];
};

export default useGroupEntitlementsTableColumns;
