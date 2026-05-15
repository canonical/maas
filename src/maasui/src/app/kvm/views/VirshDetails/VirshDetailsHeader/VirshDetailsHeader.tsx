import type { ReactElement, ReactNode } from "react";

import { Spinner } from "@canonical/react-components";
import { useSelector } from "react-redux";
import { useLocation, Link } from "react-router";

import VirshDetailsActionMenu from "./VirshDetailsActionMenu";

import { useGetZone } from "@/app/api/query/zones";
import { useFetchActions } from "@/app/base/hooks";
import urls from "@/app/base/urls";
import KVMDetailsHeader from "@/app/kvm/components/KVMDetailsHeader";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Pod["id"];
};

const VirshDetailsHeader = ({ id }: Props): ReactElement => {
  const location = useLocation();
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  // id will be of a known pod, so we can safely assume that pod will be defined
  // eslint-disable-next-line @typescript-eslint/no-non-null-asserted-optional-chain
  const zone = useGetZone({ path: { zone_id: pod?.zone! } });

  useFetchActions([podActions.fetch]);

  let title: ReactNode = <Spinner text="Loading..." />;
  if (pod) {
    title = pod.name;
  }

  return (
    <KVMDetailsHeader
      buttons={
        pod
          ? [<VirshDetailsActionMenu hostId={pod.id} key="action-dropdown" />]
          : null
      }
      loading={!pod}
      tabLinks={[
        {
          active: location.pathname.endsWith(
            urls.kvm.virsh.details.resources({ id })
          ),
          component: Link,
          label: "Resources",
          to: urls.kvm.virsh.details.resources({ id }),
        },
        {
          active: location.pathname.endsWith(
            urls.kvm.virsh.details.edit({ id })
          ),
          component: Link,
          label: "Settings",
          to: urls.kvm.virsh.details.edit({ id }),
        },
      ]}
      title={title}
      titleBlocks={
        pod
          ? [
              {
                title: "Power address:",
                subtitle: pod.power_parameters?.power_address,
              },
              {
                title: "VMs:",
                subtitle: `${pod.resources.vm_count.tracked} available`,
              },
              {
                title: "AZ:",
                subtitle: zone?.data?.name || <Spinner />,
              },
            ]
          : []
      }
    />
  );
};

export default VirshDetailsHeader;
