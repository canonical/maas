import { ContentSection } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import * as Yup from "yup";

import StorageFormFields from "./StorageFormFields";
import type { StorageFormValues } from "./types";

import {
  useConfigurations,
  useBulkSetConfigurations,
} from "@/app/api/query/configurations";
import type { PublicConfigName, SetConfigurationsError } from "@/app/apiclient";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { getConfigsFromResponse } from "@/app/settings/utils";
import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";

const StorageSchema = Yup.object().shape({
  default_storage_layout: Yup.string().required(),
  disk_erase_with_quick_erase: Yup.boolean().required(),
  disk_erase_with_secure_erase: Yup.boolean().required(),
  enable_disk_erasing_on_release: Yup.boolean().required(),
});

const StorageForm = (): React.ReactElement => {
  const names = [
    ConfigNames.DEFAULT_STORAGE_LAYOUT,
    ConfigNames.DISK_ERASE_WITH_QUICK_ERASE,
    ConfigNames.DISK_ERASE_WITH_SECURE_ERASE,
    ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
  ] as PublicConfigName[];
  const { data, isPending, error, isSuccess } = useConfigurations({
    query: {
      name: names,
    },
  });
  const eTag = data?.headers?.get("ETag");
  const {
    default_storage_layout,
    disk_erase_with_quick_erase,
    disk_erase_with_secure_erase,
    enable_disk_erasing_on_release,
  } = getConfigsFromResponse(data?.items || [], names);
  const updateConfig = useBulkSetConfigurations();
  useWindowTitle("Storage");

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Storage
        </ContentSection.Title>
        <ContentSection.Content>
          {isPending && <Spinner text="Loading..." />}
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching storage configurations"
            >
              {error.message}
            </NotificationBanner>
          )}
          {isSuccess && (
            <FormikForm<StorageFormValues, SetConfigurationsError>
              cleanup={configActions.cleanup}
              errors={updateConfig.error}
              initialValues={{
                default_storage_layout:
                  (default_storage_layout as string) || "",
                disk_erase_with_quick_erase:
                  (disk_erase_with_quick_erase as boolean) || false,
                disk_erase_with_secure_erase:
                  (disk_erase_with_secure_erase as boolean) || false,
                enable_disk_erasing_on_release:
                  (enable_disk_erasing_on_release as boolean) || false,
              }}
              onSaveAnalytics={{
                action: "Saved",
                category: "Storage settings",
                label: "Storage form",
              }}
              onSubmit={(values, { resetForm }) => {
                updateConfig.mutate({
                  headers: {
                    ETag: eTag,
                  },
                  body: {
                    configurations: [
                      {
                        name: "default_storage_layout",
                        value: values.default_storage_layout,
                      },
                      {
                        name: "disk_erase_with_quick_erase",
                        value: values.disk_erase_with_quick_erase,
                      },
                      {
                        name: "disk_erase_with_secure_erase",
                        value: values.disk_erase_with_secure_erase,
                      },
                      {
                        name: "enable_disk_erasing_on_release",
                        value: values.enable_disk_erasing_on_release,
                      },
                    ],
                  },
                });
                resetForm({ values });
              }}
              saved={updateConfig.isSuccess}
              saving={updateConfig.isPending}
              validationSchema={StorageSchema}
            >
              <StorageFormFields />
            </FormikForm>
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default StorageForm;
