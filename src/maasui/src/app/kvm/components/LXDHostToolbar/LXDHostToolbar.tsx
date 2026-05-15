import { Icon, Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useLocation, Link } from "react-router";

import { useGetPool } from "@/app/api/query/pools";
import Switch from "@/app/base/components/Switch";
import { useSendAnalytics } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import type { VMCluster } from "@/app/store/vmcluster/types";

type Props = {
  clusterId?: VMCluster["id"];
  hostId: Pod["id"];
  setViewByNuma?: (viewByNuma: boolean) => void;
  showBasic?: boolean;
  title?: string;
  viewByNuma?: boolean;
};

const LXDHostToolbar = ({
  clusterId,
  hostId,
  setViewByNuma,
  showBasic,
  title,
  viewByNuma,
}: Props): React.ReactElement | null => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const { data: pool } = useGetPool({ path: { resource_pool_id: pod!.pool } });
  const sendAnalytics = useSendAnalytics();
  const location = useLocation();

  if (!pod) {
    return null;
  }

  const inClusterView = clusterId !== undefined;
  const canViewByNuma = pod.resources.numa.length >= 1;
  // Safeguard in case local storage is set to true even though the pod has no
  // known NUMA nodes.
  const showNumaCards = viewByNuma && canViewByNuma;
  const tags = pod.tags.join(", ");
  const name = title ? title : pod.name;
  return (
    <div className="lxd-host-toolbar">
      <div className="lxd-host-toolbar__title lxd-host-toolbar__block u-truncate">
        <h2
          className="p-heading--4 u-no-margin--bottom u-no-padding--top u-truncate"
          data-testid="toolbar-title"
          title={name}
        >
          {name}
        </h2>
        {inClusterView && !showBasic && (
          <div className="u-nudge-up--x-small u-truncate">
            <Link
              data-testid="settings-link"
              state={{ from: location.pathname }}
              to={{
                pathname: urls.kvm.lxd.cluster.host.edit({
                  clusterId,
                  hostId,
                }),
              }}
            >
              <Icon name="settings" />
              <span className="u-nudge-right--small">Host settings</span>
            </Link>
          </div>
        )}
      </div>
      <div
        className="lxd-host-toolbar__block no-divider u-nudge-down--x-small"
        data-testid="lxd-version"
      >
        <p className="u-text--muted u-no-margin u-no-padding">LXD version:</p>
        <p className="u-no-margin u-no-padding">{pod.version}</p>
      </div>
      {!showBasic ? (
        <>
          <div className="lxd-host-toolbar__block u-nudge-down--x-small">
            <p className="u-text--muted u-no-margin u-no-padding">
              Resource pool:
            </p>
            <p className="u-no-margin u-no-padding" data-testid="pod-pool">
              {pool?.name || <Spinner />}
            </p>
          </div>
          <div className="lxd-host-toolbar__block u-nudge-down--x-small u-truncate">
            <p className="u-text--muted u-no-margin u-no-padding">Tags:</p>
            <p
              className="u-no-margin u-no-padding u-truncate"
              data-testid="pod-tags"
              title={tags}
            >
              {tags}
            </p>
          </div>
        </>
      ) : null}
      {canViewByNuma && setViewByNuma && !showBasic && (
        <div className="lxd-host-toolbar__switch lxd-host-toolbar__block">
          <Switch
            checked={showNumaCards}
            className="p-switch--inline-label"
            data-testid="numa-switch"
            label="View by NUMA node"
            onChange={(evt: React.ChangeEvent<HTMLInputElement>) => {
              const checked = evt.target.checked;
              setViewByNuma(checked);
              sendAnalytics(
                "LXD host VMs",
                "Toggle NUMA view",
                checked ? "View by NUMA node" : "View aggregate"
              );
            }}
          />
        </div>
      )}
    </div>
  );
};

export default LXDHostToolbar;
