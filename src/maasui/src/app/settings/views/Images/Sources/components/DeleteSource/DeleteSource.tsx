import type { ReactElement } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";

import {
  useDeleteImageSource,
  useGetImageSource,
} from "@/app/api/query/imageSources";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type DeleteSourceProps = {
  id: number;
};

const DeleteSource = ({ id }: DeleteSourceProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const source = useGetImageSource({ path: { boot_source_id: id } }, true);

  const eTag = source.data?.headers?.get("ETag");
  const deleteSource = useDeleteImageSource();

  return (
    <>
      {source.isPending && <Spinner text="Loading..." />}
      {source.isError && (
        <NotificationBanner severity="negative">
          {source.error.message}
        </NotificationBanner>
      )}
      {source.isSuccess && source.data && (
        <>
          <NotificationBanner
            className="u-no-margin--bottom"
            severity="caution"
            title="Images will be affected"
          >
            Removing a source will remove all images that were pulled from the
            source.
          </NotificationBanner>
          <ModelActionForm
            aria-label="Confirm custom source deletion"
            errors={deleteSource.error}
            initialValues={{}}
            message={
              <>
                Are you sure you want to remove{" "}
                <strong>{source.data.name}</strong> ({source.data.url})?
              </>
            }
            modelType="custom source"
            onCancel={closeSidePanel}
            onSubmit={() => {
              deleteSource.mutate({
                headers: { ETag: eTag },
                path: { boot_source_id: id },
              });
            }}
            onSuccess={closeSidePanel}
            saved={deleteSource.isSuccess}
            saving={deleteSource.isPending}
            submitLabel="Delete source"
          />
        </>
      )}
    </>
  );
};

export default DeleteSource;
