import type { Dispatch, ReactElement, SetStateAction } from "react";
import { useState, useEffect } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { RowSelectionState } from "@tanstack/react-table";

import { useGetConfiguration } from "@/app/api/query/configurations";
import { useImages } from "@/app/api/query/images";
import useImageTableColumns, {
  filterCells,
  filterHeaders,
} from "@/app/images/components/ImagesTable/useImageTableColumns/useImageTableColumns";
import { useOptimisticImages } from "@/app/images/hooks/useOptimisticImages/useOptimisticImages";
import type { OptimisticImageStatusResponse } from "@/app/images/types";
import { ConfigNames } from "@/app/store/config/types";

import "./_index.scss";

type ImagesTableProps = {
  selectedRows: RowSelectionState;
  setSelectedRows: Dispatch<SetStateAction<RowSelectionState>>;
  variant?: "full-height" | "regular";
};

const ImagesTable = ({
  selectedRows,
  setSelectedRows,
  variant,
}: ImagesTableProps): ReactElement => {
  const images = useImages();

  const [isRestoring, setIsRestoring] = useState<boolean>(true);
  const { restoreOptimisticImages: restoreStartingImages } =
    useOptimisticImages("OptimisticDownloading");
  const { restoreOptimisticImages: restoreStoppingImages } =
    useOptimisticImages("OptimisticStopping");

  const commissioningRelease =
    (useGetConfiguration({
      path: { name: ConfigNames.COMMISSIONING_DISTRO_SERIES },
    }).data?.value as string) ?? "";

  const columns = useImageTableColumns({
    commissioningRelease,
    selectedRows,
    setSelectedRows,
    isStatusLoading: images.stages.statuses.isLoading,
    isStatisticsLoading: images.stages.statistics.isLoading,
  });

  const downloadingStatuses: (
    | OptimisticImageStatusResponse["status"]
    | OptimisticImageStatusResponse["update_status"]
  )[] = ["Downloading", "OptimisticDownloading", "OptimisticStopping"];

  useEffect(() => {
    if (!images.isLoading) {
      (async () => {
        // Only restore if there are images
        if (images.data.total > 0) {
          await restoreStartingImages();
          await restoreStoppingImages();
        }
        setIsRestoring(false);
      })();
    }
  }, [
    images.isLoading,
    images.data.total,
    restoreStartingImages,
    restoreStoppingImages,
  ]);

  return (
    <GenericTable
      aria-label="Images table"
      columns={columns}
      data={images.data.items}
      filterCells={filterCells}
      filterHeaders={filterHeaders}
      groupBy={["os"]}
      isLoading={images.stages.images.isLoading || isRestoring}
      noData="No images have been selected to sync."
      pinGroup={[
        { value: "ubuntu", isTop: true },
        { value: "other", isTop: false },
      ]}
      selection={{
        rowSelection: selectedRows,
        setRowSelection: setSelectedRows,
        rowSelectionLabelKey: "title",
        filterSelectable: (row) =>
          row.original.release !== commissioningRelease &&
          !(
            downloadingStatuses.includes(
              row.original.status as OptimisticImageStatusResponse["status"]
            ) ||
            downloadingStatuses.includes(
              row.original
                .update_status as OptimisticImageStatusResponse["update_status"]
            )
          ),
        disabledSelectionTooltip: (row) =>
          row.original.release === commissioningRelease
            ? "Cannot modify images of the default commissioning release."
            : "Cannot modify images that are currently being downloaded.",
      }}
      showChevron
      sorting={[{ id: "title", desc: true }]}
      variant={variant}
    />
  );
};

export default ImagesTable;
