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

type DisableSourceProps = {
  id: number;
};

const DisableSource = ({ id }: DisableSourceProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const source = useGetImageSource({ path: { boot_source_id: id } }, true);

  const eTag = source.data?.headers?.get("ETag");
  const disableSource = useUpdateImageSource();

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
          aria-label="Confirm default source disabling"
          errors={disableSource.error}
          initialValues={{}}
          message={
            <>
              Are you sure you want to disable{" "}
              <strong>{source.data.name}</strong> ({source.data.url})?
            </>
          }
          modelType="default source"
          onCancel={closeSidePanel}
          onSubmit={() => {
            disableSource.mutate({
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
                enabled: false,
              },
            });
          }}
          onSuccess={closeSidePanel}
          saved={disableSource.isSuccess}
          saving={disableSource.isPending}
          submitLabel="Disable source"
        />
      )}
    </>
  );
};

export default DisableSource;
