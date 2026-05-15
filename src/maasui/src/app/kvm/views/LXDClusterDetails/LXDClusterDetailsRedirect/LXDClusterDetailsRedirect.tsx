import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { Navigate } from "react-router";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import { useGetURLId } from "@/app/base/hooks/urls";
import urls from "@/app/base/urls";
import podSelectors from "@/app/store/pod/selectors";
import { PodMeta } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import type { VMCluster } from "@/app/store/vmcluster/types";
import { isId } from "@/app/utils";

type Props = {
  clusterId: VMCluster["id"];
};

export enum Label {
  Loading = "Loading LXD host",
}

const LXDClusterDetailsRedirect = ({
  clusterId,
}: Props): React.ReactElement => {
  const hostId = useGetURLId(PodMeta.PK, "hostId");
  const host = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const hostsLoaded = useSelector(podSelectors.loaded);
  if (!hostsLoaded) {
    return <Spinner aria-label={Label.Loading} />;
  }
  if (!isId(hostId) || !host) {
    return (
      <ModelNotFound
        id={hostId}
        inSection={false}
        linkText="View all LXD hosts in this cluster"
        linkURL={urls.kvm.lxd.cluster.hosts({ clusterId })}
        modelName="LXD host"
      />
    );
  }
  return (
    <Navigate
      replace
      to={urls.kvm.lxd.cluster.host.edit({ clusterId, hostId })}
    />
  );
};

export default LXDClusterDetailsRedirect;
