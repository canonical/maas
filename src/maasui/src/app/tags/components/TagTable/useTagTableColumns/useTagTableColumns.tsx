import { useMemo } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Icon } from "@canonical/react-components";
import type { ColumnDef } from "@tanstack/react-table";
import { Link } from "react-router";

import { Label } from "../TagTable";

import TableActions from "@/app/base/components/TableActions";
import TooltipButton from "@/app/base/components/TooltipButton";
import docsUrls from "@/app/base/docsUrls";
import urls from "@/app/base/urls";
import type { Tag, TagMeta } from "@/app/store/tag/types";
import type { UtcDatetime } from "@/app/store/types/model";
import AppliedTo from "@/app/tags/components/AppliedTo";
import { formatUtcDatetime } from "@/app/utils/time";

export type TagTableColumnData = {
  id: number;
  name: string;
  updated: UtcDatetime;
  definition?: string;
  kernel_opts: string | null;
};

export type TagTableColumnDef = ColumnDef<
  TagTableColumnData,
  Partial<TagTableColumnData>
>;

type Props = {
  onDelete: (id: Tag[TagMeta.PK], fromDetails?: boolean) => void;
  onUpdate: (id: Tag[TagMeta.PK]) => void;
};
const useTagTableColumns = ({
  onDelete,
  onUpdate,
}: Props): TagTableColumnDef[] => {
  return useMemo(
    (): TagTableColumnDef[] => [
      {
        accessorKey: "name",
        header: "Tag name",
        cell: ({
          row: {
            original: { name, id },
          },
        }) => <Link to={urls.tags.tag.index({ id })}>{name}</Link>,
      },
      {
        accessorKey: "updated",
        header: "Last update",
        cell: ({
          row: {
            original: { updated },
          },
        }) => formatUtcDatetime(updated),
      },
      {
        accessorKey: "auto",
        header: () => (
          <>
            {Label.Auto}{" "}
            <TooltipButton
              aria-label="More about automatic tags"
              message={
                <>
                  Automatic tags are automatically applied to every
                  <br />
                  machine that matches their definition.
                  <br />
                  <ExternalLink
                    className="is-on-dark"
                    to={docsUrls.tagsAutomatic}
                  >
                    Check the documentation about automatic tags.
                  </ExternalLink>
                </>
              }
              position="top-center"
            />
          </>
        ),
        enableSorting: false,
        cell: ({
          row: {
            original: { definition },
          },
        }) =>
          definition ? (
            <Icon aria-label="Automatic tag" name="success-grey" />
          ) : null,
      },
      {
        accessorKey: "appliedTo",
        header: "Applied to",
        enableSorting: false,
        cell: ({
          row: {
            original: { id },
          },
        }) => <AppliedTo id={id} />,
      },
      {
        accessorKey: "options",
        header: "Kernel options",
        enableSorting: false,
        cell: ({
          row: {
            original: { kernel_opts },
          },
        }) => (!!kernel_opts ? <Icon name="success-grey" /> : null),
      },
      {
        accessorKey: "actions",
        header: "Actions",
        enableSorting: false,
        cell: ({
          row: {
            original: { id },
          },
        }) => (
          <TableActions
            onDelete={() => {
              onDelete(id);
            }}
            onEdit={() => {
              onUpdate(id);
            }}
          />
        ),
      },
    ],
    [onDelete, onUpdate]
  );
};

export default useTagTableColumns;
