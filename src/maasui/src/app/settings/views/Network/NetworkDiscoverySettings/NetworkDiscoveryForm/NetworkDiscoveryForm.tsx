import type { ReactElement } from "react";
import { useEffect } from "react";

import { Select, Spinner } from "@canonical/react-components";
import type { FormikContextType } from "formik";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import type { NetworkDiscoveryValues } from "./types";

import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useWindowTitle } from "@/app/base/hooks";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { NetworkDiscovery } from "@/app/store/config/types";

const NetworkDiscoverySchema = Yup.object().shape({
  active_discovery_interval: Yup.number().required(),
  network_discovery: Yup.string().required(),
});

const NetworkDiscoveryForm = (): ReactElement => {
  const dispatch = useDispatch();
  const updateConfig = configActions.update;

  const loaded = useSelector(configSelectors.loaded);
  const loading = useSelector(configSelectors.loading);
  const saved = useSelector(configSelectors.saved);
  const saving = useSelector(configSelectors.saving);
  const errors = useSelector(configSelectors.errors);

  const activeDiscoveryInterval = useSelector(
    configSelectors.activeDiscoveryInterval
  );
  const networkDiscovery = useSelector(configSelectors.networkDiscovery);
  const networkDiscoveryOptions = useSelector(
    configSelectors.networkDiscoveryOptions
  );
  const discoveryIntervalOptions = useSelector(
    configSelectors.discoveryIntervalOptions
  );

  useWindowTitle("Network discovery");

  useEffect(() => {
    if (!loaded) {
      dispatch(configActions.fetch());
    }
  }, [dispatch, loaded]);

  return (
    <>
      {loading && <Spinner text="Loading..." />}
      {loaded && (
        <FormikForm<NetworkDiscoveryValues>
          cleanup={configActions.cleanup}
          errors={errors}
          initialValues={{
            active_discovery_interval: activeDiscoveryInterval || "",
            network_discovery: networkDiscovery || "",
          }}
          onSaveAnalytics={{
            action: "Saved",
            category: "Network settings",
            label: "Network discovery form",
          }}
          onSubmit={(values, { resetForm }) => {
            if (values.network_discovery === NetworkDiscovery.DISABLED) {
              // Don't update the interval when the discovery is being disabled.
              delete values.active_discovery_interval;
            }
            dispatch(updateConfig(values));
            resetForm({ values });
          }}
          saved={saved}
          saving={saving}
          validationSchema={NetworkDiscoverySchema}
        >
          {({ values }: FormikContextType<NetworkDiscoveryValues>) => (
            <>
              <FormikField
                component={Select}
                help="When enabled, MAAS will use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets."
                label="Network discovery"
                name="network_discovery"
                options={networkDiscoveryOptions}
              />
              <FormikField
                component={Select}
                disabled={
                  values.network_discovery === NetworkDiscovery.DISABLED
                }
                help="When enabled, each rack will scan subnets enabled for active mapping. This helps ensure discovery information is accurate and complete."
                label="Active subnet mapping interval"
                name="active_discovery_interval"
                options={discoveryIntervalOptions}
              />
            </>
          )}
        </FormikForm>
      )}
    </>
  );
};

export default NetworkDiscoveryForm;
