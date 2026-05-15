import type { Dispatch, ReactElement, SetStateAction } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import type { RowSelectionState } from "@tanstack/react-table";
import pluralize from "pluralize";

import {
  useDeleteCustomImages,
  useDeleteSelections,
  useImages,
} from "@/app/api/query/images";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type DeleteImagesProps = {
  rowSelection: RowSelectionState;
  setRowSelection:
    | Dispatch<SetStateAction<RowSelectionState>>
    | null
    | undefined;
};

const DeleteImages = ({
  rowSelection,
  setRowSelection,
}: DeleteImagesProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const deleteSelections = useDeleteSelections();
  const deleteCustomImages = useDeleteCustomImages();
  const images = useImages();

  const imagesCount = Object.keys(rowSelection).length;

  const selectedImages = images.data.items.filter(
    (image) => rowSelection[image.id]
  );

  return (
    <>
      {images.isLoading && <Spinner text="Loading..." />}
      {images.isError && (
        <NotificationBanner severity="negative">
          {images.stages.images.error?.message}
        </NotificationBanner>
      )}
      <ModelActionForm
        aria-label="Confirm image deletion"
        errors={deleteSelections.error || deleteCustomImages.error}
        initialValues={{}}
        message={
          <>
            <NotificationBanner
              severity="caution"
              title="Machines will be affected"
            >
              Deleting images will affect machines using those images for
              commissioning.
            </NotificationBanner>
            <p>
              Are you sure you want to delete the following{" "}
              {pluralize("image", imagesCount)}?
            </p>
            <ul>
              {selectedImages.map((image) => (
                <li key={image.id}>
                  {image.title} ({image.architecture})
                </li>
              ))}
            </ul>
          </>
        }
        modelType="image"
        onCancel={closeSidePanel}
        onSubmit={() => {
          const selectionIds = Object.keys(rowSelection)
            .filter((id) => id.endsWith("-selection"))
            .map((id) => Number(id.split("-")[0]));
          const customImageIds = Object.keys(rowSelection)
            .filter((id) => id.endsWith("-custom"))
            .map((id) => Number(id.split("-")[0]));

          if (selectionIds.length) {
            deleteSelections.mutate({
              query: {
                id: selectionIds,
              },
            });
          }

          if (customImageIds.length) {
            deleteCustomImages.mutate({
              query: {
                id: customImageIds,
              },
            });
          }
        }}
        onSuccess={() => {
          if (setRowSelection) {
            setRowSelection({});
          }
          closeSidePanel();
        }}
        saved={deleteSelections.isSuccess || deleteCustomImages.isSuccess}
        saving={deleteSelections.isPending || deleteCustomImages.isPending}
        submitAppearance="negative"
        submitLabel={`Delete ${pluralize("image", imagesCount, true)}`}
      />
    </>
  );
};

export default DeleteImages;
