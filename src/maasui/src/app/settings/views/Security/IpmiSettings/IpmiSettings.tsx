import type { ReactElement } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import * as Yup from "yup";

import Fields from "./IpmiFormFields";

import {
  useBulkSetConfigurations,
  useConfigurations,
} from "@/app/api/query/configurations";
import type { PublicConfigName, SetConfigurationsError } from "@/app/apiclient";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { getConfigsFromResponse } from "@/app/settings/utils";
import { configActions } from "@/app/store/config";
import { AutoIpmiPrivilegeLevel, ConfigNames } from "@/app/store/config/types";

const IpmiSchema = Yup.object().shape({
  maas_auto_ipmi_user: Yup.string()
    .required(
      'The username cannot be left blank. The username is "maas" by default.'
    )
    .min(3, "The username must be 3 characters or more")
    .max(16, "The username must be 16 characters or less.")
    .matches(/^\S*$/, "The username may not contain spaces"),
  maas_auto_ipmi_k_g_bmc_key: Yup.string(),
  maas_auto_ipmi_user_privilege_level: Yup.string().matches(
    /(ADMIN|OPERATOR|USER)/
  ),
});

export enum Labels {
  FormLabel = "IPMI Form",
  Loading = "Loading...",
}

export type IpmiFormValues = {
  maas_auto_ipmi_user: string;
  maas_auto_ipmi_k_g_bmc_key: string;
  maas_auto_ipmi_user_privilege_level: AutoIpmiPrivilegeLevel;
};

const IpmiSettings = (): ReactElement => {
  const names = [
    ConfigNames.MAAS_AUTO_IPMI_USER,
    ConfigNames.MAAS_AUTO_IPMI_K_G_BMC_KEY,
    ConfigNames.MAAS_AUTO_IPMI_USER_PRIVILEGE_LEVEL,
  ] as PublicConfigName[];
  const { data, isPending, error, isSuccess } = useConfigurations({
    query: { name: names },
  });
  const eTag = data?.headers?.get("ETag");
  const {
    maas_auto_ipmi_user,
    maas_auto_ipmi_k_g_bmc_key,
    maas_auto_ipmi_user_privilege_level,
  } = getConfigsFromResponse(data?.items || [], names);
  const updateConfig = useBulkSetConfigurations();
  useWindowTitle("IPMI settings");

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          IPMI settings
        </ContentSection.Title>
        <ContentSection.Content>
          {isPending && <Spinner text={Labels.Loading} />}
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching security configurations ipmi settings"
            >
              {error.message}
            </NotificationBanner>
          )}
          {isSuccess && (
            <FormikForm<IpmiFormValues, SetConfigurationsError>
              aria-label={Labels.FormLabel}
              cleanup={configActions.cleanup}
              errors={updateConfig.error}
              initialValues={{
                maas_auto_ipmi_user: (maas_auto_ipmi_user as string) || "maas",
                maas_auto_ipmi_k_g_bmc_key:
                  (maas_auto_ipmi_k_g_bmc_key as string) || "",
                maas_auto_ipmi_user_privilege_level:
                  (maas_auto_ipmi_user_privilege_level as AutoIpmiPrivilegeLevel) ||
                  AutoIpmiPrivilegeLevel.ADMIN,
              }}
              onSaveAnalytics={{
                action: "Saved",
                category: "Configuration settings",
                label: "IPMI form",
              }}
              onSubmit={(values, { resetForm }) => {
                updateConfig.mutate({
                  headers: {
                    ETag: eTag,
                  },
                  body: {
                    configurations: [
                      {
                        name: ConfigNames.MAAS_AUTO_IPMI_USER,
                        value: values.maas_auto_ipmi_user,
                      },
                      {
                        name: ConfigNames.MAAS_AUTO_IPMI_K_G_BMC_KEY,
                        value: values.maas_auto_ipmi_k_g_bmc_key,
                      },
                      {
                        name: ConfigNames.MAAS_AUTO_IPMI_USER_PRIVILEGE_LEVEL,
                        value: values.maas_auto_ipmi_user_privilege_level,
                      },
                    ],
                  },
                });
                resetForm({ values });
              }}
              saved={updateConfig.isSuccess}
              saving={updateConfig.isPending}
              validationSchema={IpmiSchema}
            >
              <Fields />
            </FormikForm>
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default IpmiSettings;
