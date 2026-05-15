import { memo } from "react";

import { Button, Tooltip } from "@canonical/react-components";
import classNames from "classnames";
import { useSelector } from "react-redux";
import { Link } from "react-router";

import MachineCheckbox from "../MachineCheckbox";

import DoubleRow from "@/app/base/components/DoubleRow";
import MacAddressDisplay from "@/app/base/components/MacAddressDisplay";
import NonBreakingSpace from "@/app/base/components/NonBreakingSpace";
import urls from "@/app/base/urls";
import machineSelectors from "@/app/store/machine/selectors";
import type {
  Machine,
  MachineMeta,
  MachineStateListGroup,
} from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";

type Props = {
  callId?: string | null;
  groupValue: MachineStateListGroup["value"];
  showActions?: boolean;
  showMAC?: boolean;
  systemId: Machine[MachineMeta.PK];
  machines?: Machine[];
};

const generateFQDN = (machine: Machine, machineURL: string) => {
  return (
    <Link title={machine.fqdn} to={machineURL}>
      <strong data-testid="hostname">
        {machine.locked ? (
          <span title="This machine is locked. You have to unlock it to perform any actions.">
            <i aria-label="Locked" className="p-icon--locked">
              Locked:{" "}
            </i>{" "}
          </span>
        ) : null}
        {machine.hostname}
      </strong>
      <small>.{machine.domain.name}</small>
    </Link>
  );
};

const generateIPAddresses = (machine: Machine) => {
  const ipAddresses: string[] = [];
  let bootIP;

  (machine.ip_addresses || []).forEach((address) => {
    let ip = address.ip;
    if (address.is_boot) {
      ip = `${ip} (PXE)`;
      bootIP = ip;
    }
    if (!ipAddresses.includes(ip)) {
      ipAddresses.push(ip);
    }
  });

  if (ipAddresses.length) {
    const ipAddressesLine = (
      <>
        <span
          className="u-truncate"
          data-testid="ip-addresses"
          title={ipAddresses.length === 1 ? ipAddresses[0] : ""}
        >
          {bootIP || ipAddresses[0]}
        </span>
      </>
    );

    if (ipAddresses.length === 1) {
      return ipAddressesLine;
    }
    return (
      <>
        {ipAddressesLine}
        <Tooltip
          message={
            <>
              <strong>{ipAddresses.length} interfaces:</strong>
              <ul className="p-list u-no-margin--bottom">
                {ipAddresses.map((address) => (
                  <li key={address}>{address}</li>
                ))}
              </ul>
            </>
          }
          position="right"
          positionElementClassName="p-double-row__tooltip-inner"
        >
          {ipAddresses.length > 1 ? (
            <>
              (
              <Button
                appearance="link"
                className="p-double-row__button u-no-border u-no-margin u-no-padding"
              >{`+${ipAddresses.length - 1}`}</Button>
              )
            </>
          ) : null}
        </Tooltip>
      </>
    );
  }
  return "";
};

const generateMAC = (machine: Machine, machineURL: string) => {
  return (
    <>
      <Link title={machine.fqdn} to={machineURL}>
        <MacAddressDisplay>{machine.pxe_mac}</MacAddressDisplay>
      </Link>
      {machine.extra_macs && machine.extra_macs.length > 0 ? (
        <Link to={machineURL}> (+{machine.extra_macs.length})</Link>
      ) : null}
    </>
  );
};

export const NameColumn = ({
  callId,
  groupValue,
  showActions,
  showMAC,
  systemId,
  machines,
}: Props): React.ReactElement | null => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  if (!machine) {
    return null;
  }
  const machineURL = urls.machines.machine.index({ id: machine.system_id });
  const primaryRow = showMAC
    ? generateMAC(machine, machineURL)
    : generateFQDN(machine, machineURL);
  const secondaryRow = !showMAC && generateIPAddresses(machine);

  return (
    <DoubleRow
      data-testid="name-column"
      primary={
        showActions ? (
          <MachineCheckbox
            callId={callId}
            groupValue={groupValue}
            label={primaryRow}
            machines={machines ?? []}
            systemId={systemId}
          />
        ) : (
          primaryRow
        )
      }
      // fallback to non-breaking space to keep equal height of all rows
      secondary={secondaryRow || <NonBreakingSpace />}
      secondaryClassName={classNames([
        "u-flex",
        { "u-nudge--secondary-row u-align--left": showActions },
      ])}
    />
  );
};

export default memo(NameColumn);
