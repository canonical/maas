import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import StoragePopover from "@/app/kvm/components/StorageColumn/StoragePopover";
import type { KVMStoragePoolResources } from "@/app/kvm/types";
import { calcFreePoolStorage, getSortedPoolsArray } from "@/app/kvm/utils";
import type { Pod } from "@/app/store/pod/types";

type Props = {
  defaultPoolId?: Pod["default_storage_pool"];
  pools: KVMStoragePoolResources;
};

const StorageMeter = ({
  defaultPoolId,
  pools,
}: Props): React.ReactElement | null => {
  const sortedPools = getSortedPoolsArray(pools);
  // This component is only meant to show the data for a single pool, so if
  // there are any more return null.
  if (sortedPools.length !== 1) {
    return null;
  }
  const [, pool] = sortedPools[0];

  return (
    <div aria-label="storage meter" className="u-width--full">
      <StoragePopover defaultPoolId={defaultPoolId} pools={pools}>
        <KVMResourceMeter
          allocated={pool.allocated_tracked}
          detailed
          free={calcFreePoolStorage(pool)}
          other={pool.allocated_other}
          unit="B"
        />
      </StoragePopover>
    </div>
  );
};

export default StorageMeter;
