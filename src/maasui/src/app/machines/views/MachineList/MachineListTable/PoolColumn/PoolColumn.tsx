import { memo, useEffect, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router";

import { usePools } from "@/app/api/query/pools";
import type { ResourcePoolResponse } from "@/app/apiclient";
import DoubleRow from "@/app/base/components/DoubleRow";
import urls from "@/app/base/urls";
import { useToggleMenu } from "@/app/machines/hooks";
import type { MachineMenuToggleHandler } from "@/app/machines/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineMeta } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  onToggleMenu?: MachineMenuToggleHandler;
  systemId: Machine[MachineMeta.PK];
};

export const PoolColumn = ({
  onToggleMenu,
  systemId,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const [updating, setUpdating] = useState<ResourcePoolResponse["id"] | null>(
    null
  );
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const { data: resourcePools } = usePools();
  const toggleMenu = useToggleMenu(onToggleMenu || null);

  let poolLinks;
  const machinePools = resourcePools?.items.filter(
    (pool) => pool.id !== machine?.pool.id
  );
  if (machine?.actions.includes(NodeActions.SET_POOL)) {
    if (machinePools?.length !== 0) {
      poolLinks = machinePools?.map((pool) => ({
        children: pool.name,
        "data-testid": "change-pool-link",
        onClick: () => {
          dispatch(
            machineActions.setPool({
              pool_id: pool.id,
              system_id: systemId,
            })
          );
          setUpdating(pool.id);
        },
      }));
    } else {
      poolLinks = [{ children: "No other pools available", disabled: true }];
    }
  } else {
    poolLinks = [
      { children: "Cannot change pool of this machine", disabled: true },
    ];
  }

  useEffect(() => {
    if (updating !== null && machine?.pool.id === updating) {
      setUpdating(null);
    }
  }, [updating, machine?.pool.id]);

  if (!machine) {
    return null;
  }

  return (
    <DoubleRow
      menuLinks={onToggleMenu && poolLinks}
      menuTitle="Change pool:"
      onToggleMenu={toggleMenu}
      primary={
        <span data-testid="pool">
          {updating !== null ? (
            <Spinner className="u-nudge-left--small" />
          ) : null}
          <Link className="p-link--soft" to={urls.pools.index}>
            {machine.pool.name}
          </Link>
        </span>
      }
      primaryAriaLabel="Pool"
      primaryTitle={machine.pool.name}
      secondary={
        <span data-testid="note" title={machine.description}>
          {machine.description}
        </span>
      }
      secondaryAriaLabel="Note"
      secondaryTitle={machine.description}
    />
  );
};

export default memo(PoolColumn);
