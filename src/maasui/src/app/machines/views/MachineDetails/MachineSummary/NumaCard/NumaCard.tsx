import { Card, List, Spinner } from "@canonical/react-components";
import pluralize from "pluralize";
import { useSelector } from "react-redux";

import NumaCardDetails from "./NumaCardDetails";

import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import { isMachineDetails } from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";

type Props = {
  id: Machine["system_id"];
};

export enum Labels {
  NumaCard = "Numa nodes",
  NumaList = "Numa nodes list",
}

const NumaCard = ({ id }: Props): React.ReactElement => {
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, id)
  );
  let numaNodeString = "NUMA node";
  let content: React.ReactElement | null;

  // Confirm that the full machine details have been fetched. This also allows
  // TypeScript know we're using the right union type (otherwise it will
  // complain that numa_nodes doesn't exist on the base machine type).
  if (!isMachineDetails(machine)) {
    content = <Spinner />;
  } else {
    const numaNodes = machine.numa_nodes;
    numaNodeString = pluralize("NUMA node", numaNodes.length, true);
    content = numaNodes.length ? (
      <List
        aria-label={Labels.NumaList}
        className="u-no-margin--bottom  p-list--divided"
        items={numaNodes.map((numaNode, i) => ({
          className: "numa-card__list",
          content: (
            <NumaCardDetails
              isLast={i === numaNodes.length - 1}
              machineId={id}
              numaNode={numaNode}
              showExpanded={numaNodes.length <= 2}
            />
          ),
        }))}
      />
    ) : null;
  }

  return (
    <div className="machine-summary__numa-card">
      <Card aria-label={Labels.NumaCard} className="numa-card">
        <div className="u-sv1 p-muted-heading">{numaNodeString}</div>
        {content}
      </Card>
    </div>
  );
};

export default NumaCard;
