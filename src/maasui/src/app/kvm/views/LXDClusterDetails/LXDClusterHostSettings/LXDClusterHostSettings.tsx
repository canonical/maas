import { useEffect } from "react";

import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useNavigate } from "react-router";

import ModelNotFound from "@/app/base/components/ModelNotFound";
import { useGetURLId, useWindowTitle } from "@/app/base/hooks";
import type { SyncNavigateFunction } from "@/app/base/types";
import urls from "@/app/base/urls";
import KVMConfigurationCard from "@/app/kvm/components/KVMConfigurationCard";
import LXDHostToolbar from "@/app/kvm/components/LXDHostToolbar";
import SettingsBackLink from "@/app/kvm/components/SettingsBackLink";
import { useActivePod, useKVMDetailsRedirect } from "@/app/kvm/hooks";
import podSelectors from "@/app/store/pod/selectors";
import { PodMeta } from "@/app/store/pod/types";
import { isPodDetails } from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";
import vmClusterSelectors from "@/app/store/vmcluster/selectors";
import type { VMCluster } from "@/app/store/vmcluster/types";
import { isId } from "@/app/utils";

type Props = {
  clusterId: VMCluster["id"];
};

export enum Label {
  Loading = "Loading LXD host",
  Title = "LXD cluster host settings",
}

const LXDClusterHostSettings = ({ clusterId }: Props): React.ReactElement => {
  const navigate: SyncNavigateFunction = useNavigate();
  const hostId = useGetURLId(PodMeta.PK, "hostId");
  const cluster = useSelector((state: RootState) =>
    vmClusterSelectors.getById(state, clusterId)
  );
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const loading = useSelector(podSelectors.loading);
  useActivePod(hostId);
  const redirectURL = useKVMDetailsRedirect(hostId);
  useWindowTitle(
    `${pod?.name || "Host"} in ${cluster?.name || "cluster"} settings`
  );

  useEffect(() => {
    if (redirectURL) {
      navigate(redirectURL, { replace: true });
    }
  }, [navigate, redirectURL]);

  if (loading) {
    return <Spinner aria-label={Label.Loading} />;
  }
  if (!isId(hostId) || !pod || !isPodDetails(pod)) {
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
    <Strip aria-label={Label.Title} className="u-no-padding--top" shallow>
      <SettingsBackLink />
      <LXDHostToolbar clusterId={clusterId} hostId={hostId} showBasic />
      <KVMConfigurationCard pod={pod} zoneDisabled />
    </Strip>
  );
};

export default LXDClusterHostSettings;
