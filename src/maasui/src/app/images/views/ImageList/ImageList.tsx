import type { ReactElement } from "react";
import { useState } from "react";

import { Notification as NotificationBanner } from "@canonical/react-components";
import type { RowSelectionState } from "@tanstack/react-table";

import ImageListHeader from "./ImageListHeader";

import { useGetConfiguration } from "@/app/api/query/configurations";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import ImagesTable from "@/app/images/components/ImagesTable";
import { ConfigNames } from "@/app/store/config/types";

export enum Labels {
  SyncDisabled = "Automatic image updates are disabled. This may mean that images won't be automatically updated and receive the latest package versions and security fixes.",
}

const ImageList = (): ReactElement => {
  const { data, isPending } = useGetConfiguration({
    path: { name: ConfigNames.BOOT_IMAGES_AUTO_IMPORT },
  });
  const autoImport = data?.value as boolean;
  const configLoaded = !isPending;

  const [selectedRows, setSelectedRows] = useState<RowSelectionState>({});

  useWindowTitle("Images");

  return (
    <PageContent
      header={
        <ImageListHeader
          selectedRows={selectedRows}
          setSelectedRows={setSelectedRows}
        />
      }
    >
      {configLoaded && (
        <>
          {!autoImport && (
            <NotificationBanner
              data-testid="disabled-sync-warning"
              severity="caution"
            >
              {Labels.SyncDisabled}
            </NotificationBanner>
          )}
          <ImagesTable
            selectedRows={selectedRows}
            setSelectedRows={setSelectedRows}
          />
        </>
      )}
    </PageContent>
  );
};

export default ImageList;
