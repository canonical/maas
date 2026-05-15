import type { Dispatch, ReactElement, SetStateAction } from "react";

import { MainToolbar } from "@canonical/maas-react-components";
import { Button, Spinner } from "@canonical/react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import pluralize from "pluralize";

import { useImageSources } from "@/app/api/query/imageSources";
import { useSelectionStatuses } from "@/app/api/query/images";
import type { BootSourceResponse } from "@/app/apiclient";
import { useSidePanel } from "@/app/base/side-panel-context";
import DeleteImages from "@/app/images/components/DeleteImages";
import SelectUpstreamImagesForm from "@/app/images/components/SelectUpstreamImagesForm";
import UploadCustomImage from "@/app/images/components/UploadCustomImage";
import { MAAS_IO_URLS } from "@/app/images/constants";

type ImageListHeaderProps = {
  selectedRows: RowSelectionState;
  setSelectedRows: Dispatch<SetStateAction<RowSelectionState>>;
};

const getImageSyncText = (sources: BootSourceResponse[]) => {
  if (sources.length === 1) {
    const mainSource = sources[0];
    if (new RegExp(MAAS_IO_URLS.stable).test(mainSource.url ?? "")) {
      return "maas.io";
    } else if (new RegExp(MAAS_IO_URLS.candidate).test(mainSource.url ?? "")) {
      return "maas.io (candidate)";
    }
    return mainSource.url;
  }
  return "multiple sources";
};

const ImageListHeader = ({
  selectedRows,
  setSelectedRows,
}: ImageListHeaderProps): ReactElement => {
  const { openSidePanel } = useSidePanel();

  const sources = useImageSources();
  const selectionsStatuses = useSelectionStatuses();

  const isPending = sources.isPending || selectionsStatuses.isPending;
  const isDeleteDisabled = Object.keys(selectedRows).length <= 0;

  const selectedImageCount = Object.values(selectedRows).filter(
    (isSelected) => isSelected
  ).length;

  return (
    <MainToolbar>
      <>
        <MainToolbar.Title>
          Images synced from{" "}
          <strong>{getImageSyncText(sources.data?.items ?? [])}</strong>
        </MainToolbar.Title>
        {isPending ? <Spinner text="Loading..." /> : null}
        <MainToolbar.Controls>
          <Button
            appearance="negative"
            disabled={isDeleteDisabled}
            hasIcon
            onClick={() => {
              openSidePanel({
                component: DeleteImages,
                title: `Delete ${selectedImageCount > 1 ? `${selectedImageCount} ` : ""}${pluralize("image", selectedImageCount)}`,
                props: {
                  rowSelection: selectedRows,
                  setRowSelection: setSelectedRows,
                },
              });
            }}
            type="button"
          >
            <i className="p-icon--delete is-light" />
            <span>Delete</span>
          </Button>
          <Button
            hasIcon
            onClick={() => {
              openSidePanel({
                component: UploadCustomImage,
                title: "Upload custom image",
              });
            }}
            type="button"
          >
            <i className="p-icon--upload" />
            <span>Upload custom image</span>
          </Button>
          <Button
            hasIcon
            onClick={() => {
              openSidePanel({
                component: SelectUpstreamImagesForm,
                title: "Select upstream images to sync",
              });
            }}
            type="button"
          >
            <i className="p-icon--begin-downloading" />
            <span>Select upstream images</span>
          </Button>
        </MainToolbar.Controls>
      </>
    </MainToolbar>
  );
};

export default ImageListHeader;
