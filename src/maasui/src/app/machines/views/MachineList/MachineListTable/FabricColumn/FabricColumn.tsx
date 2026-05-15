import { memo } from "react";

import { useSelector } from "react-redux";
import { Link } from "react-router";

import MachineTestStatus from "../MachineTestStatus";

import DoubleRow from "@/app/base/components/DoubleRow";
import urls from "@/app/base/urls";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = { systemId: Machine["system_id"] };

export const FabricColumn = ({
  systemId,
}: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );

  if (machine) {
    const fabricID = machine.vlan && machine.vlan.fabric_id;
    const fabricName = machine.vlan && machine.vlan.fabric_name;
    const vlan = machine.vlan && machine.vlan.name ? machine.vlan.name : "";

    return (
      <DoubleRow
        primary={
          <MachineTestStatus
            data-testid="fabric"
            status={machine.network_test_status.status}
            tooltipPosition="top-left"
          >
            {fabricName && (fabricID || fabricID === 0) ? (
              <Link
                className="p-link--soft"
                to={urls.networks.fabric.index({ id: fabricID })}
              >
                {fabricName}
              </Link>
            ) : (
              "-"
            )}
          </MachineTestStatus>
        }
        primaryAriaLabel="Fabric"
        primaryTitle={fabricName}
        secondary={<span data-testid="vlan">{vlan}</span>}
        secondaryAriaLabel="VLAN"
        secondaryTitle={vlan}
      />
    );
  }
  return null;
};

export default memo(FabricColumn);
