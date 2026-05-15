import { useMemo } from "react";

import { ModularTable } from "@canonical/react-components";
import type { ColumnWithLooseAccessor } from "react-table";

import { columnLabels, ControllerVLANsColumns } from "./constants";
import { useControllerVLANsTable } from "./hooks";
import type { ControllerTableData } from "./types";

import ControllerLink from "@/app/base/components/ControllerLink";
import FabricLink from "@/app/base/components/FabricLink";
import SubnetLink from "@/app/base/components/SubnetLink";
import VLANLink from "@/app/base/components/VLANLink";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { Subnet } from "@/app/store/subnet/types";

type Props = {
  systemId: Controller[ControllerMeta.PK];
};

const ControllerVLANsTable = ({ systemId }: Props): React.ReactElement => {
  const { data, loaded } = useControllerVLANsTable({ systemId });

  return (
    <ModularTable
      aria-label="Controller VLANs"
      className="controller-vlans-table"
      columns={useMemo(
        () =>
          [
            {
              Header: columnLabels[ControllerVLANsColumns.FABRIC],
              accessor: ControllerVLANsColumns.FABRIC,
              Cell: ({
                value,
              }: {
                value: ControllerTableData[ControllerVLANsColumns.FABRIC];
              }) => <FabricLink id={value?.id} />,
            },
            {
              Header: columnLabels[ControllerVLANsColumns.VLAN],
              accessor: ControllerVLANsColumns.VLAN,
              Cell: ({
                value,
              }: {
                value: ControllerTableData[ControllerVLANsColumns.VLAN];
              }) => <VLANLink id={value?.id} />,
            },
            {
              Header: columnLabels[ControllerVLANsColumns.DHCP],
              accessor: ControllerVLANsColumns.DHCP,
            },
            {
              Header: columnLabels[ControllerVLANsColumns.SUBNET],
              accessor: ControllerVLANsColumns.SUBNET,
              Cell: ({
                value,
              }: {
                value: ControllerTableData[ControllerVLANsColumns.SUBNET];
              }) => (
                <>
                  {value?.map(({ id }: Subnet) => (
                    <div key={id}>
                      <SubnetLink id={id} />
                    </div>
                  ))}
                </>
              ),
            },
            {
              Header: columnLabels[ControllerVLANsColumns.PRIMARY_RACK],
              accessor: ControllerVLANsColumns.PRIMARY_RACK,
              Cell: ({
                value,
              }: {
                value: ControllerTableData[ControllerVLANsColumns.PRIMARY_RACK];
              }) => <ControllerLink systemId={value} />,
            },
            {
              Header: columnLabels[ControllerVLANsColumns.SECONDARY_RACK],
              accessor: ControllerVLANsColumns.SECONDARY_RACK,
              Cell: ({
                value,
              }: {
                value: ControllerTableData[ControllerVLANsColumns.SECONDARY_RACK];
              }) => <ControllerLink systemId={value} />,
            },
          ] as ColumnWithLooseAccessor[],
        []
      )}
      data={data}
      emptyMsg={loaded ? "No VLANs found" : "Loading..."}
    />
  );
};

export default ControllerVLANsTable;
