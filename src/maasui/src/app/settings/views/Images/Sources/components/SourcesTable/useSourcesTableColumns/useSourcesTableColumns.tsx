import { useMemo } from "react";

import { ContextualMenu, Icon, Tooltip } from "@canonical/react-components";
import type { Column, ColumnDef, Header, Row } from "@tanstack/react-table";
import pluralize from "pluralize";

import { useSidePanel } from "@/app/base/side-panel-context";
import { MAAS_IO_URLS } from "@/app/images/constants";
import { BootResourceSourceType } from "@/app/images/types";
import type { ImageSource } from "@/app/settings/views/Images/Sources/Sources";
import DeleteSource from "@/app/settings/views/Images/Sources/components/DeleteSource";
import DisableSource from "@/app/settings/views/Images/Sources/components/DisableSource";
import EditSource from "@/app/settings/views/Images/Sources/components/EditSource";
import EnableSource from "@/app/settings/views/Images/Sources/components/EnableSource";

type SourcesColumnDef = ColumnDef<ImageSource, Partial<ImageSource>>;

export const filterCells = (
  row: Row<ImageSource>,
  column: Column<ImageSource>
): boolean => {
  if (row.getIsGrouped()) {
    return ["type"].includes(column.id);
  } else {
    return !["type"].includes(column.id);
  }
};

export const filterHeaders = (header: Header<ImageSource, unknown>): boolean =>
  header.column.id !== "type";

const useSourcesTableColumns = ({
  canChangeSource,
}: {
  canChangeSource: boolean;
}): SourcesColumnDef[] => {
  const { openSidePanel } = useSidePanel();

  return useMemo(
    () =>
      [
        {
          id: "type",
          accessorKey: "type",
          cell: ({ row }: { row: Row<ImageSource> }) => {
            return (
              <div>
                <div>
                  <strong>
                    {row.original.type === BootResourceSourceType.MAAS_IO
                      ? "MAAS Images"
                      : "Custom Images"}
                  </strong>
                </div>
                <small className="u-text--muted">
                  {pluralize("source", row.getLeafRows().length ?? 0, true)}
                </small>
              </div>
            );
          },
        },
        {
          id: "name",
          accessorKey: "name",
          enableSorting: true,
          header: "Name",
          cell: ({
            row: {
              original: { type, url, name, enabled },
            },
          }: {
            row: Row<ImageSource>;
          }) => {
            if (type === BootResourceSourceType.MAAS_IO) {
              const label = new RegExp(MAAS_IO_URLS.stable).test(url)
                ? "MAAS Stable"
                : "MAAS Candidate";
              return (
                <>
                  {!enabled && (
                    <Tooltip
                      className="disabled-source-tooltip"
                      message="This default source is disabled."
                    >
                      <Icon name="help" />
                    </Tooltip>
                  )}
                  {label}
                </>
              );
            }
            return name;
          },
        },
        {
          id: "url",
          accessorKey: "url",
          enableSorting: true,
          header: "Source URL",
        },
        {
          id: "priority",
          accessorKey: "priority",
          enableSorting: true,
          header: () => {
            return (
              <>
                Priority
                <Tooltip
                  message="If the same image is available from several sources,
                           the image from the source with the higher priority
                           takes precedence. 1 is the highest priority."
                >
                  <Icon name="help" />
                </Tooltip>
              </>
            );
          },
        },
        {
          id: "signed",
          accessorKey: "signed",
          enableSorting: true,
          header: "Signed with GPG key",
          cell: ({
            row: {
              original: { keyring_filename, keyring_data },
            },
          }) =>
            keyring_filename?.length || keyring_data?.length ? (
              <Icon name="success-grey" />
            ) : (
              <Icon name="error-grey" />
            ),
        },
        {
          id: "actions",
          accessorKey: "id",
          enableSorting: false,
          header: "Actions",
          cell: ({ row: { original } }) => {
            return (
              <ContextualMenu
                hasToggleIcon={true}
                links={[
                  {
                    children: "Edit source...",
                    onClick: () => {
                      openSidePanel({
                        component: EditSource,
                        title: `Edit ${original.type === BootResourceSourceType.MAAS_IO ? "default" : "custom"} source`,
                        props: {
                          id: original.id,
                          isDefault:
                            original.type === BootResourceSourceType.MAAS_IO,
                        },
                      });
                    },
                  },
                  original.type === BootResourceSourceType.CUSTOM
                    ? {
                        children: "Delete source...",
                        onClick: () => {
                          openSidePanel({
                            component: DeleteSource,
                            title: "Delete custom source",
                            props: { id: original.id },
                          });
                        },
                      }
                    : original.enabled
                      ? {
                          children: "Disable source...",
                          onClick: () => {
                            openSidePanel({
                              component: DisableSource,
                              title: "Disable default source",
                              props: { id: original.id },
                            });
                          },
                        }
                      : {
                          children: "Enable source...",
                          onClick: () => {
                            openSidePanel({
                              component: EnableSource,
                              title: "Enable default source",
                              props: { id: original.id },
                            });
                          },
                        },
                ]}
                toggleAppearance="base"
                toggleClassName="row-menu-toggle u-no-margin--bottom"
                toggleDisabled={!canChangeSource}
              />
            );
          },
        },
      ] as SourcesColumnDef[],
    [canChangeSource, openSidePanel]
  );
};

export default useSourcesTableColumns;
