import type { ReactElement } from "react";
import { useCallback } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
  Strip,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router";

import FormikForm from "@/app/base/components/FormikForm";
import { useCycled } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";

type MapSubnetProps = {
  subnetId: number;
};

export const MapSubnet = ({
  subnetId,
}: MapSubnetProps): ReactElement | null => {
  const { closeSidePanel } = useSidePanel();
  const dispatch = useDispatch();
  const cleanup = useCallback(() => subnetActions.cleanup(), []);
  const subnet = useSelector((state: RootState) =>
    subnetSelectors.getById(state, subnetId)
  );
  const scanError = useSelector((state: RootState) =>
    subnetSelectors.eventErrorsForSubnets(state, subnetId, "scan")
  )[0]?.error;
  const scanning = useSelector((state: RootState) =>
    subnetSelectors.getStatusForSubnet(state, subnetId, "scanning")
  );
  const [scanned, resetScanned] = useCycled(!scanning);
  const saved = scanned && !scanError;

  if (!subnet) {
    return (
      <Strip data-testid="loading-subnet" shallow>
        <Spinner text="Loading..." />
      </Strip>
    );
  }

  const isIPv4 = subnet.version === 4;
  return (
    <FormikForm<EmptyObject>
      cleanup={cleanup}
      errors={scanError}
      initialValues={{}}
      onCancel={closeSidePanel}
      onSubmit={() => {
        resetScanned();
        dispatch(cleanup());
        dispatch(subnetActions.scan(subnetId));
      }}
      onSuccess={closeSidePanel}
      saved={saved}
      saving={scanning}
      submitDisabled={!isIPv4}
      submitLabel="Map subnet"
    >
      {isIPv4 ? (
        <>
          You will start mapping your subnet. Go to the{" "}
          <Link to={urls.networkDiscovery.index}>dashboard</Link> to see the
          discovered items.
        </>
      ) : (
        <NotificationBanner
          borderless
          inline
          severity="negative"
          title="Error:"
        >
          Only IPv4 subnets can be scanned.
        </NotificationBanner>
      )}
    </FormikForm>
  );
};

export default MapSubnet;
