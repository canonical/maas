import type { ReactElement } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import classNames from "classnames";

import DoughnutChart from "@/app/base/components/DoughnutChart";
import { COLOURS } from "@/app/base/constants";
import useRamResourcesColumns from "@/app/kvm/components/RamResources/useRamResourcesColumns/useRamResourcesColumns";
import { memoryWithUnit } from "@/app/kvm/utils";

export type RamResourcesProps = {
  dynamicLayout?: boolean;
  generalAllocated: number; // B
  generalFree: number; // B
  generalOther?: number; // B
  hugepagesAllocated?: number; // B
  hugepagesFree?: number; // B
  hugepagesOther?: number; // B
  pageSize?: number; // B
};

export type RamResource = {
  id: number;
  type: "General" | "Hugepage";
  allocated: number;
  others: number;
  free: number;
};

const getTooltipSubstring = (general: number, hugepages: number) =>
  `${memoryWithUnit(general)} general${
    hugepages > 0 ? ` + ${memoryWithUnit(hugepages)} hugepages` : ""
  }`;

const RamResources = ({
  dynamicLayout = false,
  generalAllocated,
  generalFree,
  generalOther = 0,
  hugepagesAllocated = 0,
  hugepagesFree = 0,
  hugepagesOther = 0,
  pageSize = 0,
}: RamResourcesProps): ReactElement => {
  const totalGeneral = generalAllocated + generalFree + generalOther;
  const totalHugepages = hugepagesAllocated + hugepagesFree + hugepagesOther;
  const totalMemory = totalGeneral + totalHugepages;
  const overCommitted = generalFree < 0 || hugepagesFree < 0;
  const showOthers = generalOther > 0 || hugepagesOther > 0;
  const showHugepages = totalHugepages > 0;

  const columns = useRamResourcesColumns({ pageSize, showOthers });
  const data: RamResource[] = [
    {
      id: 0,
      type: "General",
      allocated: generalAllocated,
      others: generalOther,
      free: generalFree,
    } as RamResource,
    ...(showHugepages
      ? [
          {
            id: 1,
            type: "Hugepage",
            allocated: hugepagesAllocated,
            others: hugepagesOther,
            free: hugepagesFree,
          } as RamResource,
        ]
      : []),
  ];

  return (
    <div
      aria-label="ram resources"
      className={classNames("ram-resources", {
        "ram-resources--dynamic-layout": dynamicLayout,
      })}
    >
      <div className="ram-resources__chart-container">
        <h4 className="p-heading--small">RAM</h4>
        <DoughnutChart
          className="ram-resources__chart"
          label={memoryWithUnit(totalMemory)}
          segmentHoverWidth={18}
          segmentWidth={15}
          segments={
            overCommitted
              ? [
                  {
                    color: COLOURS.CAUTION,
                    value: 1,
                  },
                ]
              : [
                  {
                    color: COLOURS.LINK,
                    tooltip: `Allocated: ${getTooltipSubstring(
                      generalAllocated,
                      hugepagesAllocated
                    )}`,
                    value: generalAllocated + hugepagesAllocated,
                  },
                  ...(showOthers
                    ? [
                        {
                          color: COLOURS.POSITIVE,
                          tooltip: `Others: ${getTooltipSubstring(
                            generalOther,
                            hugepagesOther
                          )}`,
                          value: generalOther + hugepagesOther,
                        },
                      ]
                    : []),
                  {
                    color: COLOURS.LINK_FADED,
                    tooltip: `Free: ${getTooltipSubstring(
                      generalFree,
                      hugepagesFree
                    )}`,
                    value: generalFree + hugepagesFree,
                  },
                ]
          }
          size={96}
        />
      </div>
      <div className="ram-resources__table-container">
        <GenericTable
          aria-label="ram resources table"
          className="ram-resources__table"
          columns={columns}
          data={data}
          isLoading={false}
        />
      </div>
    </div>
  );
};

export default RamResources;
