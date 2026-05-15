import { useMemo, useState } from "react";

import { GenericTable } from "@canonical/maas-react-components";
import type { ColumnDef, RowSelectionState } from "@tanstack/react-table";
import pluralize from "pluralize";

import { useGetRack } from "@/app/api/query/racks";
import ControllerLink from "@/app/base/components/ControllerLink";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { Controller } from "@/app/store/controller/types";
import "./_index.scss";

type RemoveControllersProps = {
  id: number;
};

type RemoveControllersRow = Pick<Controller, "fqdn" | "id" | "system_id">;

type RemoveControllersColumnDef = ColumnDef<
  RemoveControllersRow,
  Partial<RemoveControllersRow>
>;

const RemoveControllers = ({ id }: RemoveControllersProps) => {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const { closeSidePanel } = useSidePanel();
  const rack = useGetRack({ path: { rack_id: id } });
  const column = useMemo(
    (): RemoveControllersColumnDef[] => [
      {
        id: "name",
        accessorKey: "system_id",
        enableSorting: true,
        header: "CONTROLLER",
        cell: ({
          row: {
            original: { system_id },
          },
        }) => <ControllerLink systemId={system_id} />,
      },
    ],
    []
  );
  // TODO when endpoint is ready: https://warthogs.atlassian.net/browse/MAASENG-5529
  const fakeControllers = useMemo(() => {
    if (rack.data) {
      return [
        {
          id: rack.data.id,
          system_id: "abcdef",
          fqdn: `controller-${rack.data.id}`,
        },
        {
          id: rack.data.id + 1,
          system_id: "ghijkl",
          fqdn: `controller-${rack.data.id + 1}`,
        },
        {
          id: rack.data.id + 2,
          system_id: "mnoprs",
          fqdn: `controller-${rack.data.id + 2}`,
        },
      ];
    } else {
      return rack.data;
    }
  }, [rack.data]);
  return (
    <FormikForm
      className="remove-controllers"
      initialValues={rowSelection}
      onCancel={closeSidePanel}
      onSubmit={() => {}}
      submitAppearance="negative"
      submitLabel={`Remove ${Object.values(rowSelection).length} ${pluralize("controller", Object.values(rowSelection).length)}`}
    >
      Are you sure you want to remove controllers from this rack? You will have
      to re-register the controllers to revert this action.
      {fakeControllers && (
        <GenericTable
          className="u-border u-margin-top--medium"
          columns={column}
          data={fakeControllers}
          isLoading={rack.isPending}
          selection={{
            rowSelection,
            setRowSelection,
            rowSelectionLabelKey: "fqdn",
          }}
        />
      )}
    </FormikForm>
  );
};

export default RemoveControllers;
