import StoragePopover from "./StoragePopover";

import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import type { KVMResource, KVMStoragePoolResources } from "@/app/kvm/types";
import type { Pod } from "@/app/store/pod/types";

type Props = {
  defaultPoolId?: Pod["default_storage_pool"];
  pools: KVMStoragePoolResources;
  storage: KVMResource;
};

const StorageColumn = ({
  defaultPoolId,
  pools,
  storage,
}: Props): React.ReactElement | null => {
  return (
    <StoragePopover defaultPoolId={defaultPoolId} pools={pools}>
      <KVMResourceMeter
        allocated={storage.allocated_tracked}
        free={storage.free}
        other={storage.allocated_other}
        unit="B"
      />
    </StoragePopover>
  );
};

export default StorageColumn;
