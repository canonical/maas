import { useEffect } from "react";

import { ContentSection } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import ProxyFormFields from "../ProxyFormFields";

import type { ProxyFormValues } from "./types";

import FormikForm from "@/app/base/components/FormikForm";
import PageContent from "@/app/base/components/PageContent";
import { useWindowTitle } from "@/app/base/hooks";
import { UrlSchema } from "@/app/base/validation";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import type { ConfigValues } from "@/app/store/config/types";

const ProxySchema = Yup.object().shape({
  proxyType: Yup.string().required(),
  httpProxy: Yup.string().when("proxyType", {
    is: (val: string) => val === "externalProxy" || val === "peerProxy",
    then: UrlSchema.required("Please enter the proxy URL."),
  }),
});

const ProxyForm = (): React.ReactElement => {
  const dispatch = useDispatch();
  const updateConfig = configActions.update;

  const loaded = useSelector(configSelectors.loaded);
  const loading = useSelector(configSelectors.loading);
  const saved = useSelector(configSelectors.saved);
  const saving = useSelector(configSelectors.saving);
  const errors = useSelector(configSelectors.errors);

  const httpProxy = useSelector(configSelectors.httpProxy);
  const proxyType = useSelector(configSelectors.proxyType);

  useWindowTitle("Proxy");

  useEffect(() => {
    if (!loaded) {
      dispatch(configActions.fetch());
    }
  }, [dispatch, loaded]);

  return (
    <PageContent>
      <ContentSection variant="narrow">
        <ContentSection.Title className="section-header__title">
          Proxy
        </ContentSection.Title>
        <ContentSection.Content>
          {loading && <Spinner text="Loading..." />}
          {loaded && (
            <FormikForm<ProxyFormValues>
              cleanup={configActions.cleanup}
              errors={errors}
              initialValues={{
                httpProxy: httpProxy || "",
                proxyType,
              }}
              onSaveAnalytics={{
                action: "Saved",
                category: "Network settings",
                label: "Proxy form",
              }}
              onSubmit={(values, { resetForm }) => {
                const { httpProxy, proxyType } = values;

                let formattedValues: Record<string, ConfigValues>;
                switch (proxyType) {
                  case "builtInProxy":
                    formattedValues = {
                      http_proxy: "",
                      enable_http_proxy: true,
                      use_peer_proxy: false,
                    };
                    break;
                  case "externalProxy":
                    formattedValues = {
                      http_proxy: httpProxy,
                      enable_http_proxy: true,
                      use_peer_proxy: false,
                    };
                    break;
                  case "peerProxy":
                    formattedValues = {
                      http_proxy: httpProxy,
                      enable_http_proxy: true,
                      use_peer_proxy: true,
                    };
                    break;
                  case "noProxy":
                  default:
                    formattedValues = {
                      http_proxy: "",
                      enable_http_proxy: false,
                      use_peer_proxy: false,
                    };
                    break;
                }
                dispatch(updateConfig(formattedValues));
                resetForm({ values });
              }}
              saved={saved}
              saving={saving}
              validationSchema={ProxySchema}
            >
              <ProxyFormFields />
            </FormikForm>
          )}
        </ContentSection.Content>
      </ContentSection>
    </PageContent>
  );
};

export default ProxyForm;
