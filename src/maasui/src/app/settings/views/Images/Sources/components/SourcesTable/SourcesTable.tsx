import type { ReactElement } from "react";
import { useMemo } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import { Notification as NotificationBanner } from "@canonical/react-components";

import { useGetConfiguration } from "@/app/api/query/configurations";
import { useImageSources } from "@/app/api/query/imageSources";
import {
  useCustomImageStatuses,
  useSelectionStatuses,
} from "@/app/api/query/images";
import usePagination from "@/app/base/hooks/usePagination/usePagination";
import { MAAS_IO_URLS } from "@/app/images/constants";
import { BootResourceSourceType } from "@/app/images/types";
import type { ImageSource } from "@/app/settings/views/Images/Sources/Sources";
import useSourcesTableColumns, {
  filterCells,
  filterHeaders,
} from "@/app/settings/views/Images/Sources/components/SourcesTable/useSourcesTableColumns/useSourcesTableColumns";
import { ConfigNames } from "@/app/store/config/types";

import "./_index.scss";

const getSourceType = (url: string): BootResourceSourceType => {
  const isMaasIo =
    new RegExp(MAAS_IO_URLS.stable).test(url) ||
    new RegExp(MAAS_IO_URLS.candidate).test(url);
  return isMaasIo
    ? BootResourceSourceType.MAAS_IO
    : BootResourceSourceType.CUSTOM;
};

const SourcesTable = (): ReactElement => {
  const { page, debouncedPage, size, handlePageSizeChange, setPage } =
    usePagination();

  const sources = useImageSources({
    query: { page: debouncedPage, size },
  });
  const importConfig = useGetConfiguration({
    path: { name: ConfigNames.BOOT_IMAGES_AUTO_IMPORT },
  });

  const { data: selectionStatuses, error: selectionStatusesError } =
    useSelectionStatuses();
  const { data: customImageStatuses, error: customImageStatusesError } =
    useCustomImageStatuses();

  const loading = sources.isPending || importConfig.isPending;

  const canChangeSource =
    !!selectionStatuses &&
    !!customImageStatuses &&
    [...selectionStatuses.items, ...customImageStatuses.items].every(
      (s) => s.status !== "Downloading" && s.update_status !== "Downloading"
    );

  const errors =
    sources.error ||
    selectionStatusesError ||
    customImageStatusesError ||
    importConfig.error;

  const columns = useSourcesTableColumns({ canChangeSource });

  const data = useMemo((): ImageSource[] => {
    if (!sources.data) {
      return [];
    }
    return sources.data?.items.map((item) => ({
      ...item,
      type: getSourceType(item.url),
    }));
  }, [sources.data]);

  return (
    <>
      {!canChangeSource && (
        <NotificationBanner
          data-testid="cannot-change-source-warning"
          severity="caution"
        >
          Image import is in progress, cannot change source settings.
        </NotificationBanner>
      )}
      {errors && (
        <NotificationBanner severity="negative">
          {errors.details?.length ? errors.details[0].message : errors.message}
        </NotificationBanner>
      )}
      <GenericTable
        aria-label="Source table"
        className="sources-table"
        columns={columns}
        data={data}
        filterCells={filterCells}
        filterHeaders={filterHeaders}
        groupBy={["type"]}
        isLoading={loading}
        noData="No sources found."
        pagination={{
          currentPage: page,
          dataContext: "sources",
          handlePageSizeChange: handlePageSizeChange,
          isPending: sources.isPending,
          itemsPerPage: size,
          setCurrentPage: setPage,
          totalItems: sources.data?.total ?? 0,
        }}
        pinGroup={[{ value: BootResourceSourceType.MAAS_IO, isTop: true }]}
        showChevron
        sorting={[{ id: "priority", desc: false }]}
      />
    </>
  );
};

export default SourcesTable;
