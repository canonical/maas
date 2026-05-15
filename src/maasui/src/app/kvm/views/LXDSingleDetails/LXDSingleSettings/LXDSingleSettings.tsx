import type { ReactElement } from "react";

import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import AuthenticationCard from "./AuthenticationCard";
import DangerZoneCard from "./DangerZoneCard";

import { usePools } from "@/app/api/query/pools";
import { useZones } from "@/app/api/query/zones";
import { useFetchActions, useWindowTitle } from "@/app/base/hooks";
import KVMConfigurationCard from "@/app/kvm/components/KVMConfigurationCard";
import LXDHostToolbar from "@/app/kvm/components/LXDHostToolbar";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import { isPodDetails } from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import tagSelectors from "@/app/store/tag/selectors";

type Props = {
  id: Pod["id"];
};

export enum Label {
  Title = "LXD settings",
}

const LXDSingleSettings = ({ id }: Props): ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  const resourcePools = usePools();
  const tagsLoaded = useSelector(tagSelectors.loaded);
  const zones = useZones();
  const loaded = !resourcePools.isPending && tagsLoaded && !zones.isPending;
  useWindowTitle(`LXD ${`${pod?.name} ` || ""} settings`);

  useFetchActions([tagActions.fetch]);

  if (!isPodDetails(pod) || !loaded) {
    return <Spinner text="Loading..." />;
  }
  return (
    <Strip aria-label={Label.Title} className="u-no-padding--top" shallow>
      <LXDHostToolbar hostId={id} showBasic />
      <KVMConfigurationCard pod={pod} />
      <AuthenticationCard hostId={id} objectName={pod?.name} />
      <DangerZoneCard
        hostId={id}
        message={
          <>
            <p>
              <strong>Remove this KVM host</strong>
            </p>
            <p>
              Once a KVM host is removed, you can still access this project from
              the LXD server.
            </p>
          </>
        }
      />
    </Strip>
  );
};

export default LXDSingleSettings;
