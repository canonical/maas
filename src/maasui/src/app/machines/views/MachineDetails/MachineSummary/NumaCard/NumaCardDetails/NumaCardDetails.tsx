import { useState } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import classNames from "classnames";
import pluralize from "pluralize";
import { useSelector } from "react-redux";

import LabelledList from "@/app/base/components/LabelledList";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { NodeNumaNode } from "@/app/store/types/node";
import { getRanges } from "@/app/utils";

type Props = {
  isLast?: boolean;
  machineId: Machine["system_id"];
  numaNode: NodeNumaNode;
  showExpanded?: boolean;
};

export enum Labels {
  CpuCores = "CPU cores",
  Memory = "Memory",
  Storage = "Storage",
  Network = "Network",
  Details = "Node details",
}

const NumaCardDetails = ({
  isLast = false,
  machineId,
  numaNode,
  showExpanded = false,
}: Props): React.ReactElement => {
  const [isExpanded, setIsExpanded] = useState(showExpanded);
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, machineId)
  );

  if (!isMachineDetails(machine)) {
    return <Spinner />;
  }

  const numaDisks = (machine.disks || []).filter(
    (disk) => disk.numa_node === numaNode.index
  );
  const numaInterfaces = (machine.interfaces || []).filter(
    (iface) => iface.numa_node === numaNode.index
  );
  const coresRanges = getRanges(numaNode.cores).join(", ");
  const formattedMemory = formatBytes(
    { value: numaNode.memory, unit: "MiB" },
    { binary: true }
  );
  const totalStorage = formatBytes({
    value: numaDisks.reduce((acc, disk) => acc + disk.size, 0),
    unit: "B",
  });

  return (
    <>
      {showExpanded ? (
        <span>Node {numaNode.index}</span>
      ) : (
        <button
          className={classNames("numa-card__button", {
            "is-open": isExpanded,
          })}
          onClick={() => {
            setIsExpanded(!isExpanded);
          }}
        >
          Node {numaNode.index}
        </button>
      )}
      {isExpanded ? (
        <LabelledList
          items={[
            {
              label: Labels.CpuCores,
              value: (
                <>
                  <span>{numaNode.cores.length}</span>
                  {numaNode.cores.length ? (
                    <>
                      {" "}
                      <span className="u-text--light">({coresRanges})</span>
                    </>
                  ) : null}
                </>
              ),
            },
            {
              label: Labels.Memory,
              value: `${formattedMemory.value} ${formattedMemory.unit}`,
            },
            {
              label: Labels.Storage,
              value: `${totalStorage.value} ${
                totalStorage.unit
              } over ${pluralize("disk", numaDisks.length, true)}`,
            },
            {
              label: Labels.Network,
              value: pluralize("interface", numaInterfaces.length, true),
            },
          ]}
        />
      ) : (
        <span
          aria-label={Labels.Details}
          className="numa-card__collapsed-details"
        >
          {pluralize("core", numaNode.cores.length, true)},{" "}
          {`${formattedMemory.value} ${formattedMemory.unit}`},<br />
          {totalStorage.value} {totalStorage.unit},{" "}
          {pluralize("interface", numaInterfaces.length, true)}
        </span>
      )}
      {isLast ? null : (
        <hr
          className={classNames({
            "u-sv1": !isExpanded,
            "u-sv2": isExpanded,
          })}
        />
      )}
    </>
  );
};

export default NumaCardDetails;
