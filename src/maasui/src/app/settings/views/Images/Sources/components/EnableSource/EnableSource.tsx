import type { ReactElement } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";

import {
  useGetImageSource,
  useUpdateImageSource,
} from "@/app/api/query/imageSources";
import ModelActionForm from "@/app/base/components/ModelActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type EnableSourceProps = {
  id: number;
};

const EnableSource = ({ id }: EnableSourceProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const source = useGetImageSource({ path: { boot_source_id: id } }, true);

  const eTag = source.data?.headers?.get("ETag");
  const enableSource = useUpdateImageSource();

  return (
    <>
      {source.isPending && <Spinner text="Loading..." />}
      {source.isError && (
        <NotificationBanner severity="negative">
          {source.error.message}
        </NotificationBanner>
      )}
      {source.isSuccess && source.data && (
        <ModelActionForm
          aria-label="Confirm default source enabling"
          errors={enableSource.error}
          initialValues={{}}
          message={
            <>
              <strong>{source.data.name}</strong> will now be used to download
              images.
            </>
          }
          modelType="default source"
          onCancel={closeSidePanel}
          onSubmit={() => {
            enableSource.mutate({
              headers: { ETag: eTag },
              path: { boot_source_id: id },
              body: {
                name: source.data.name,
                url: source.data.url,
                keyring_filename: source.data.keyring_filename,
                keyring_data: source.data.keyring_data,
                skip_keyring_verification:
                  source.data.skip_keyring_verification,
                priority: source.data.priority,
                enabled: true,
              },
            });
          }}
          onSuccess={closeSidePanel}
          saved={enableSource.isSuccess}
          saving={enableSource.isPending}
          submitAppearance="positive"
          submitLabel="Enable source"
        />
      )}
    </>
  );
};

export default EnableSource;
