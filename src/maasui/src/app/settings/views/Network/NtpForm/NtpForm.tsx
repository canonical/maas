import type { ReactElement } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import * as Yup from "yup";

import {
  useBulkSetConfigurations,
  useConfigurations,
} from "@/app/api/query/configurations";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { getConfigsFromResponse } from "@/app/settings/utils";
import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";

const NtpSchema = Yup.object().shape({
  ntp_external_only: Yup.boolean().required(),
  ntp_servers: Yup.string(),
});

const NtpForm = (): ReactElement => {
  const { data, error, isPending, isError } = useConfigurations({
    query: { name: [ConfigNames.NTP_EXTERNAL_ONLY, ConfigNames.NTP_SERVERS] },
  });
  const eTag = data?.headers?.get("ETag");
  const updateConfig = useBulkSetConfigurations();

  useWindowTitle("NTP");

  if (isPending) {
    return <Spinner text="Loading..." />;
  }

  if (isError) {
    return (
      <NotificationBanner
        severity="negative"
        title="Error while fetching configurations:"
      >
        {error.message}
      </NotificationBanner>
    );
  }

  const { ntp_external_only: ntpExternalOnly, ntp_servers: ntpServers } =
    getConfigsFromResponse(data?.items ?? [], [
      ConfigNames.NTP_EXTERNAL_ONLY,
      ConfigNames.NTP_SERVERS,
    ]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          NTP
        </ContentSection.Title>
        <ContentSection.Content>
          <FormikForm
            cleanup={configActions.cleanup}
            errors={updateConfig.error}
            initialValues={{
              ntp_external_only: ntpExternalOnly ?? false,
              ntp_servers: ntpServers ?? "",
            }}
            onSaveAnalytics={{
              action: "Saved",
              category: "Network settings",
              label: "NTP form",
            }}
            onSubmit={(values, { resetForm }) => {
              updateConfig.mutate(
                {
                  headers: {
                    ETag: eTag,
                  },
                  body: {
                    configurations: [
                      {
                        name: "ntp_external_only",
                        value: values.ntp_external_only,
                      },
                      { name: "ntp_servers", value: values.ntp_servers },
                    ],
                  },
                },
                {
                  onSuccess: () => {
                    resetForm({ values });
                  },
                }
              );
            }}
            saved={updateConfig.isSuccess}
            saving={updateConfig.isPending}
            validationSchema={NtpSchema}
          >
            <FormikField
              help="NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS's DHCP services."
              label="Addresses of NTP servers"
              name="ntp_servers"
              type="text"
            />
            <FormikField
              help="Configure all region controller hosts, rack controller hosts, and subsequently deployed machines to refer directly to the configured external NTP servers. Otherwise only region controller hosts will be configured to use those external NTP servers, rack contoller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers."
              label="Use external NTP servers only"
              name="ntp_external_only"
              type="checkbox"
            />
          </FormikForm>
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default NtpForm;
