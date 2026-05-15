import type { ReactElement } from "react";

import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useStorageState } from "react-storage-hooks";

import LXDHostToolbar from "../LXDHostToolbar";

import NumaResources from "./NumaResources";

import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import ComposeForm from "@/app/kvm/components/ComposeForm";
import LXDVMsSummaryCard from "@/app/kvm/components/LXDVMsSummaryCard";
import LXDVMsTable from "@/app/kvm/components/LXDVMsTable";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import type { VMCluster } from "@/app/store/vmcluster/types";

type Props = {
  clusterId?: VMCluster["id"];
  hostId: Pod["id"];
  searchFilter: string;
  setSearchFilter: SetSearchFilter;
};

const LXDHostVMs = ({
  clusterId,
  hostId,
  searchFilter,
  setSearchFilter,
  ...wrapperProps
}: Props): ReactElement => {
  const { openSidePanel } = useSidePanel();
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const [viewByNuma, setViewByNuma] = useStorageState(
    localStorage,
    `viewPod${hostId}ByNuma`,
    false
  );
  const isInCluster = !!clusterId || clusterId === 0;

  if (pod) {
    return (
      <div {...wrapperProps}>
        <LXDHostToolbar
          clusterId={clusterId}
          hostId={hostId}
          setViewByNuma={setViewByNuma}
          title={isInCluster ? `VMs on ${pod.name}` : "VMs on this host"}
          viewByNuma={viewByNuma}
        />
        {viewByNuma ? (
          <NumaResources id={hostId} />
        ) : (
          <LXDVMsSummaryCard id={hostId} />
        )}
        <Strip shallow>
          <LXDVMsTable
            getResources={(vm) => {
              const resources =
                pod.resources.vms.find(
                  ({ system_id }) => system_id === vm.system_id
                ) || null;
              return {
                hugepagesBacked: resources?.hugepages_backed || false,
                pinnedCores: resources?.pinned_cores || [],
                unpinnedCores: resources?.unpinned_cores || 0,
              };
            }}
            onAddVMClick={() => {
              openSidePanel({
                component: ComposeForm,
                title: "Compose",
                props: { hostId },
              });
            }}
            pods={[pod.name]}
            searchFilter={searchFilter}
            setSearchFilter={setSearchFilter}
          />
        </Strip>
      </div>
    );
  }
  return <Spinner text="Loading..." />;
};

export default LXDHostVMs;
