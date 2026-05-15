import type { ReactElement } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import {
  Notification as NotificationBanner,
  NotificationSeverity,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import { useClearNetworkDiscoveries } from "@/app/api/query/networkDiscovery";
import type { ClearAllDiscoveriesWithOptionalIpAndMacError } from "@/app/apiclient";
import FormikForm from "@/app/base/components/FormikForm";
import docsUrls from "@/app/base/docsUrls";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import configSelectors from "@/app/store/config/selectors";
import { NetworkDiscovery } from "@/app/store/config/types";
import { messageActions } from "@/app/store/message";

export enum Labels {
  SubmitLabel = "Clear all discoveries",
}

const ClearAllForm = (): ReactElement => {
  const { closeSidePanel } = useSidePanel();

  const dispatch = useDispatch();
  const networkDiscovery = useSelector(configSelectors.networkDiscovery);
  const clearDiscovery = useClearNetworkDiscoveries();
  let content: ReactElement;
  if (networkDiscovery === NetworkDiscovery.ENABLED) {
    content = (
      <>
        <p data-testid="enabled-message">
          MAAS will use passive techniques (such as listening to ARP requests
          and mDNS advertisements) to observe networks attached to rack
          controllers.
          <br />
          If active subnet mapping is enabled on the configured subnets, MAAS
          will actively scan them and ensure discovery information is accurate
          and complete.
        </p>
        <p>
          Learn more about{" "}
          <ExternalLink to={docsUrls.networkDiscovery}>
            network discovery
          </ExternalLink>
          .
        </p>
      </>
    );
  } else {
    content = (
      <p data-testid="disabled-message">
        Network discovery is disabled. The list of discovered items will not be
        repopulated.
      </p>
    );
  }
  return (
    <FormikForm<EmptyObject, ClearAllDiscoveriesWithOptionalIpAndMacError>
      aria-label="Clear all discoveries"
      errors={clearDiscovery.error}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Network discovery",
        category: "Clear network discoveries",
        label: "Clear network discoveries button",
      }}
      onSubmit={() => {
        clearDiscovery.mutate({});
      }}
      onSuccess={() => {
        dispatch(
          messageActions.add(
            "All discoveries cleared.",
            NotificationSeverity.INFORMATION
          )
        );
        closeSidePanel();
      }}
      saved={clearDiscovery.isSuccess}
      saving={clearDiscovery.isPending}
      secondarySubmitLabel="Save and add another"
      submitAppearance="negative"
      submitLabel={Labels.SubmitLabel}
    >
      <NotificationBanner
        severity={NotificationSeverity.CAUTION}
        title="Warning:"
      >
        Clearing all discoveries will remove all items from the list below.
      </NotificationBanner>
      {content}
    </FormikForm>
  );
};

export default ClearAllForm;
