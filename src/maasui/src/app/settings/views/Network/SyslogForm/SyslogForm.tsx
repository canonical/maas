import type { ReactElement } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import {
  Spinner,
  Notification as NotificationBanner,
} from "@canonical/react-components";
import * as Yup from "yup";

import {
  useSetConfiguration,
  useGetConfiguration,
} from "@/app/api/query/configurations";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";
import { ConfigNames } from "@/app/store/config/types";

const SyslogSchema = Yup.object().shape({
  remote_syslog: Yup.string(),
});

const SyslogForm = (): ReactElement => {
  const { data, isPending, error, isSuccess } = useGetConfiguration({
    path: { name: ConfigNames.REMOTE_SYSLOG },
  });
  const eTag = data?.headers?.get("ETag");
  const remote_syslog = data?.value || "";
  const updateConfig = useSetConfiguration();

  useWindowTitle("Syslog");

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Syslog
        </ContentSection.Title>
        <ContentSection.Content>
          {isPending && <Spinner text="Loading..." />}
          {error && (
            <NotificationBanner
              severity="negative"
              title="Error while fetching network configurations"
            >
              {error.message}
            </NotificationBanner>
          )}
          {isSuccess && (
            <FormikForm
              cleanup={configActions.cleanup}
              errors={updateConfig.error}
              initialValues={{
                remote_syslog,
              }}
              onSaveAnalytics={{
                action: "Saved",
                category: "Network settings",
                label: "Syslog form",
              }}
              onSubmit={(values, { resetForm }) => {
                updateConfig.mutate({
                  headers: {
                    ETag: eTag,
                  },
                  body: {
                    value: values.remote_syslog,
                  },
                  path: { name: ConfigNames.REMOTE_SYSLOG },
                });
                resetForm({ values });
              }}
              saved={updateConfig.isSuccess}
              saving={updateConfig.isPending}
              validationSchema={SyslogSchema}
            >
              <FormikField
                help="A remote syslog server that MAAS will set on enlisting, commissioning, testing, and deploying machines to send all log messages. Clearing this value will restore the default behaviour of forwarding syslog to MAAS."
                label="Remote syslog server to forward machine logs"
                name="remote_syslog"
                type="text"
              />
            </FormikForm>
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default SyslogForm;
