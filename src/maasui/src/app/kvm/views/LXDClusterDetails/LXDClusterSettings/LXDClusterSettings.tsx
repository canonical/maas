import { Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useWindowTitle } from "@/app/base/hooks";
import { useActivePod } from "@/app/kvm/hooks";
import AuthenticationCard from "@/app/kvm/views/LXDSingleDetails/LXDSingleSettings/AuthenticationCard";
import DangerZoneCard from "@/app/kvm/views/LXDSingleDetails/LXDSingleSettings/DangerZoneCard";
import type { RootState } from "@/app/store/root/types";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster } from "@/app/store/vmcluster/types";

type Props = {
  clusterId: VMCluster["id"];
};

export enum Label {
  Title = "LXD cluster settings",
}

const LXDClusterSettings = ({ clusterId }: Props): React.ReactElement => {
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  useActivePod(cluster?.hosts[0]?.id || null);
  useWindowTitle(`${cluster?.name || "Cluster"} settings`);

  return (
    <Strip aria-label={Label.Title} shallow>
      <AuthenticationCard
        hostId={cluster?.hosts[0]?.id || null}
        objectName={cluster?.name || null}
      />
      <DangerZoneCard
        clusterId={clusterId}
        message={
          <>
            <p>
              <strong>Remove this LXD cluster</strong>
            </p>
            <p>
              All KVM hosts in this LXD cluster will be removed, you can still
              access this project from the LXD server.
            </p>
          </>
        }
      />
    </Strip>
  );
};

export default LXDClusterSettings;
