import { useGetPool } from "@/app/api/query/pools";
import { useGetZone } from "@/app/api/query/zones";
import type { ResourcePoolResponse, ZoneResponse } from "@/app/apiclient";
import DoubleRow from "@/app/base/components/DoubleRow";

type Props = {
  poolId?: ResourcePoolResponse["id"] | null;
  zoneId?: ZoneResponse["id"] | null;
};

const PoolColumn = ({ poolId, zoneId }: Props): React.ReactElement | null => {
  const { data: pool } = useGetPool({ path: { resource_pool_id: poolId! } });
  const { data: zone } = useGetZone({ path: { zone_id: zoneId! } });

  return (
    <DoubleRow
      primary={<span data-testid="pool">{pool?.name}</span>}
      secondary={<span data-testid="zone">{zone?.name}</span>}
    />
  );
};

export default PoolColumn;
