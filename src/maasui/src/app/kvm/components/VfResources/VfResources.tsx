import type { ReactElement, ReactNode } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import classNames from "classnames";

import KVMResourceMeter from "@/app/kvm/components/KVMResourceMeter";
import useVfResourcesColumns from "@/app/kvm/components/VfResources/useVfResourcesColumns/useVfResourcesColumns";
import type { PodNetworkInterface, PodResource } from "@/app/store/pod/types";
import { simpleSortByKey } from "@/app/utils";

export type Props = {
  dynamicLayout?: boolean;
  interfaces: PodNetworkInterface[];
  showAggregated?: boolean;
};

const VfResources = ({
  dynamicLayout = false,
  interfaces,
  showAggregated = false,
}: Props): ReactElement => {
  const columns = useVfResourcesColumns();

  let content: ReactNode;
  if (showAggregated) {
    const [allocatedVFs, freeVFs, otherVFs] = interfaces.reduce<
      [
        PodResource["allocated_tracked"],
        PodResource["free"],
        PodResource["allocated_other"],
      ]
    >(
      ([allocated, free, other], { virtual_functions }) => {
        allocated += virtual_functions.allocated_tracked;
        free += virtual_functions.free;
        other += virtual_functions.allocated_other;
        return [allocated, free, other];
      },
      [0, 0, 0]
    );
    content = (
      <>
        <h4 className="p-text--x-small-capitalised">Virtual functions</h4>
        <div aria-label="vf-resources-meter" className="vf-resources__meter">
          <KVMResourceMeter
            allocated={allocatedVFs}
            detailed
            free={freeVFs}
            other={otherVFs}
            segmented
          />
        </div>
      </>
    );
  } else {
    content = (
      <div className="vf-resources__table-container">
        <h4 className="p-text--x-small-capitalised">Virtual functions</h4>
        <GenericTable
          aria-label="vf-resources-table"
          className="vf-resources__table"
          columns={columns}
          data={[...interfaces].sort(simpleSortByKey("name"))}
          isLoading={false}
          noData="No interfaces available."
          variant="regular"
        />
      </div>
    );
  }
  return (
    <div
      aria-label="VF resources"
      className={classNames("vf-resources", {
        "vf-resources--dynamic-layout": dynamicLayout,
      })}
    >
      {content}
    </div>
  );
};

export default VfResources;
