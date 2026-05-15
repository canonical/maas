import type { ReactElement } from "react";
import { useEffect } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import {
  Spinner,
  Select,
  Notification as NotificationBanner,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import {
  useBulkSetConfigurations,
  useConfigurations,
} from "@/app/api/query/configurations";
import type { PublicConfigName } from "@/app/apiclient";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { getConfigsFromResponse } from "@/app/settings/utils";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { ConfigNames } from "@/app/store/config/types";

const DnsSchema = Yup.object().shape({
  // TODO: Client-side IP validation, or display error from server
  // https://github.com/canonical/maas-ui/issues/39
  upstream_dns: Yup.string(),
  dnssec_validation: Yup.string().required(),
  dns_trusted_acl: Yup.string(),
});

const DnsForm = (): ReactElement => {
  const dispatch = useDispatch();
  const names = [
    ConfigNames.DNSSEC_VALIDATION,
    ConfigNames.DNS_TRUSTED_ACL,
    ConfigNames.UPSTREAM_DNS,
  ] as PublicConfigName[];

  const { data, isPending, error, isSuccess } = useConfigurations({
    query: { name: names },
  });
  const eTag = data?.headers?.get("ETag");

  const { dnssec_validation, dns_trusted_acl, upstream_dns } =
    getConfigsFromResponse(data?.items || [], names);
  const dnssecOptions = useSelector(configSelectors.dnssecOptions);

  const updateConfig = useBulkSetConfigurations();

  useWindowTitle("DNS");

  useEffect(() => {
    if (!isSuccess) {
      dispatch(configActions.fetch());
    }
  }, [dispatch, isSuccess]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          DNS
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
                dnssec_validation: dnssec_validation || "",
                dns_trusted_acl: dns_trusted_acl || "",
                upstream_dns: upstream_dns || "",
              }}
              onSaveAnalytics={{
                action: "Saved",
                category: "Network settings",
                label: "DNS form",
              }}
              onSubmit={(values, { resetForm }) => {
                updateConfig.mutate({
                  headers: {
                    ETag: eTag,
                  },
                  body: {
                    configurations: [
                      {
                        name: ConfigNames.DNSSEC_VALIDATION,
                        value: values.dnssec_validation,
                      },
                      {
                        name: ConfigNames.DNS_TRUSTED_ACL,
                        value: values.dns_trusted_acl,
                      },
                      {
                        name: ConfigNames.UPSTREAM_DNS,
                        value: [values.upstream_dns],
                      },
                    ],
                  },
                });
                resetForm({ values });
              }}
              saved={isSuccess}
              saving={isPending}
              validationSchema={DnsSchema}
            >
              <FormikField
                help="Only used when MAAS is running its own DNS server. This value is used as the value of 'forwarders' in the DNS server config."
                label="Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses)"
                name="upstream_dns"
                type="text"
              />
              <FormikField
                component={Select}
                help="Only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config."
                label="Enable DNSSEC validation of upstream zones"
                name="dnssec_validation"
                options={dnssecOptions}
              />
              <FormikField
                help="MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows to add extra networks (not previously known) to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names."
                label="List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution"
                name="dns_trusted_acl"
                type="text"
              />
            </FormikForm>
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default DnsForm;
