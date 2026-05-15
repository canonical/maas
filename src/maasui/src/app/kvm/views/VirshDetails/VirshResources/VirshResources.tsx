import { Spinner, Strip } from "@canonical/react-components";
import { useSelector } from "react-redux";

import { useWindowTitle } from "@/app/base/hooks";
import KVMResourcesCard from "@/app/kvm/components/KVMResourcesCard";
import KVMStorageCards from "@/app/kvm/components/KVMStorageCards";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Pod["id"];
};

export enum Label {
  Title = "Virsh resources",
}

const VirshResources = ({ id }: Props): React.ReactElement => {
  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, id)
  );
  useWindowTitle(`Virsh resources ${pod?.name || ""}`);

  if (!pod) {
    return <Spinner text="Loading" />;
  }
  return (
    <div aria-label={Label.Title}>
      <Strip shallow>
        <KVMResourcesCard id={pod.id} />
      </Strip>
      <Strip shallow>
        <KVMStorageCards
          defaultPoolId={pod.default_storage_pool}
          pools={pod.resources.storage_pools}
        />
      </Strip>
    </div>
  );
};

export default VirshResources;
