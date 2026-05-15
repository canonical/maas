import { memo, useEffect, useState } from "react";

import { Spinner, Tooltip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link } from "react-router";

import { useZones } from "@/app/api/query/zones";
import type { ZoneResponse } from "@/app/apiclient";
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

const getSpaces = (machine: Machine) => {
  if (machine.spaces.length > 1) {
    const sorted = [...machine.spaces].sort();
    return (
      <Tooltip message={sorted.join("\n")} position="btm-left">
        <span data-testid="spaces">{`${machine.spaces.length} spaces`}</span>
      </Tooltip>
    );
  }
  return (
    <span data-testid="spaces" title={machine.spaces[0]}>
      {machine.spaces[0]}
    </span>
  );
};

export const ZoneColumn = ({
  onToggleMenu,
  systemId,
}: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const [updating, setUpdating] = useState<ZoneResponse["id"] | null>(null);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const zones = useZones();
  const toggleMenu = useToggleMenu(onToggleMenu || null);
  let zoneLinks;
  const machineZones = zones.data?.items?.filter(
    (zone) => zone.id !== machine?.zone.id
  );
  if (machine?.actions.includes(NodeActions.SET_ZONE)) {
    if (machineZones?.length !== 0) {
      zoneLinks = machineZones?.map((zone) => ({
        children: zone.name,
        "data-testid": "change-zone-link",
        onClick: () => {
          dispatch(
            machineActions.setZone({
              system_id: systemId,
              zone_id: zone.id,
            })
          );
          setUpdating(zone.id);
        },
      }));
    } else {
      zoneLinks = [{ children: "No other zones available", disabled: true }];
    }
  } else {
    zoneLinks = [
      { children: "Cannot change zone of this machine", disabled: true },
    ];
  }

  useEffect(() => {
    if (updating !== null && machine?.zone.id === updating) {
      setUpdating(null);
    }
  }, [updating, machine?.zone.id]);

  if (!machine) {
    return null;
  }

  return (
    <DoubleRow
      menuLinks={onToggleMenu && zoneLinks}
      menuTitle="Change AZ:"
      onToggleMenu={toggleMenu}
      primary={
        <span data-testid="zone">
          {updating !== null ? (
            <Spinner className="u-nudge-left--small" />
          ) : null}
          <Link className="p-link--soft" to={urls.zones.index}>
            {machine.zone.name}
          </Link>
        </span>
      }
      primaryTitle={machine.zone.name}
      secondary={getSpaces(machine)}
    />
  );
};

export default memo(ZoneColumn);
