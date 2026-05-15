import type { ReactElement } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useLocation } from "react-router";
import type { Action, Dispatch } from "redux";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionConfirmationText from "@/app/base/components/NodeActionConfirmationText";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { EmptyObject } from "@/app/base/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

const DeleteVM = (): ReactElement => {
  const dispatch = useDispatch<Dispatch<Action>>();
  const location = useLocation();
  const { closeSidePanel } = useSidePanel();

  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );

  const selectedMachines = useSelector(machineSelectors.selected);
  const { selectedCount, selectedCountLoading } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );

  const {
    dispatch: dispatchForSelectedMachines,
    actionStatus,
    actionErrors,
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });

  const handleSubmit = () => {
    dispatchForSelectedMachines(machineActions.delete);
  };

  const clearSelectedMachines = () => {
    dispatch(machineActions.setSelected(null));
    dispatch(machineActions.invalidateQueries());
  };

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.DELETE}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<EmptyObject>
        actionName={NodeActions.DELETE}
        actionStatus={actionStatus}
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{}}
        modelName="VM"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: "VM action form",
          label: "Delete",
        }}
        onSubmit={handleSubmit}
        onSuccess={() => {
          closeSidePanel();
          clearSelectedMachines();
        }}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount}
        submitAppearance="negative"
      >
        <NodeActionConfirmationText
          action={NodeActions.DELETE}
          modelName="virtual machine"
          selectedCount={selectedCount}
        />
      </ActionForm>
    </>
  );
};

export default DeleteVM;
