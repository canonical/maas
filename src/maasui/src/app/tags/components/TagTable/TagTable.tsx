import type { ReactNode } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type {
  MainTableProps,
  PropsWithSpread,
} from "@canonical/react-components";
import { Strip } from "@canonical/react-components";

import type { TagTableColumnData } from "./useTagTableColumns/useTagTableColumns";
import useTagTableColumns from "./useTagTableColumns/useTagTableColumns";

import { useFetchActions } from "@/app/base/hooks";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { tagActions } from "@/app/store/tag";
import { TagSearchFilter } from "@/app/store/tag/selectors";
import type { Tag, TagMeta } from "@/app/store/tag/types";

type Props = PropsWithSpread<
  {
    filter: TagSearchFilter;
    onDelete: (id: Tag[TagMeta.PK], fromDetails?: boolean) => void;
    onUpdate: (id: Tag[TagMeta.PK]) => void;
    searchText: string;
    tags: Tag[];
  },
  MainTableProps
>;

export enum Label {
  Actions = "Actions",
  AppliedTo = "Applied to",
  Auto = "Auto",
  Name = "Tag name",
  Options = "Kernel options",
  Updated = "Last update",
}

export enum TestId {
  NoTags = "no-tags",
}

const generateNoTagsMessage = (
  noTags: boolean,
  filter: TagSearchFilter,
  searchText: string
) => {
  const hasFilter = filter !== TagSearchFilter.All;
  let noTagsMessage: ReactNode = null;
  if (noTags && (searchText || hasFilter)) {
    let filterName: string | null = null;
    if (hasFilter) {
      filterName = filter === TagSearchFilter.Auto ? "automatic" : "manual";
    }
    let message: string | null = null;
    if (hasFilter && !searchText) {
      message = `There are no ${filterName} tags.`;
    } else if (searchText) {
      message = `No${
        filterName ? ` ${filterName}` : ""
      } tags match the search criteria.`;
    }
    if (message) {
      noTagsMessage = (
        <Strip
          data-testid={TestId.NoTags}
          rowClassName="u-align--center"
          shallow
        >
          {message}
        </Strip>
      );
    }
  }
  return noTagsMessage;
};

const TagTable = ({
  filter,
  onDelete,
  onUpdate,
  searchText,
  tags,
}: Props): React.ReactElement => {
  const { page, size, handlePageSizeChange, setPage } = usePagination(50);

  useFetchActions([tagActions.fetch]);

  const columns = useTagTableColumns({ onDelete, onUpdate });
  const data: TagTableColumnData[] = tags.map((tag) => ({
    id: tag.id,
    name: tag.name,
    kernel_opts: tag.kernel_opts,
    updated: tag.updated,
    definition: tag.definition,
  }));

  return (
    <GenericTable
      columns={columns}
      data={data.slice((page - 1) * size, page * size)}
      isLoading={false}
      noData={generateNoTagsMessage(tags.length === 0, filter, searchText)}
      pagination={{
        currentPage: page,
        dataContext: "tags",
        handlePageSizeChange: handlePageSizeChange,
        isPending: false,
        itemsPerPage: size,
        setCurrentPage: setPage,
        totalItems: tags.length ?? 0,
      }}
      sorting={[{ id: "name", desc: false }]}
    />
  );
};

export default TagTable;
