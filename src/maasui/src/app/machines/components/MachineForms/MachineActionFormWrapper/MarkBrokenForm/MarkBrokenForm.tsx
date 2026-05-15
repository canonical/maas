import type { ReactElement } from "react";
import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useLocation } from "react-router";
import * as Yup from "yup";

import MarkBrokenFormFields from "./MarkBrokenFormFields";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

const MarkBrokenSchema = Yup.object().shape({
  comment: Yup.string(),
});

type MarkBrokenFormValues = {
  comment: string;
};

type MarkBrokenFormProps = {
  isViewingDetails: boolean;
};

export const MarkBrokenForm = ({
  isViewingDetails,
}: MarkBrokenFormProps): ReactElement => {
  const dispatch = useDispatch();
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
    actionErrors,
    actionStatus,
    ...actionProps
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });

  useEffect(
    () => () => {
      dispatch(machineActions.cleanup());
    },
    [dispatch]
  );

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.MARK_BROKEN}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<MarkBrokenFormValues, MachineEventErrors>
        actionName={NodeActions.MARK_BROKEN}
        allowAllEmpty
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{
          comment: "",
        }}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
          label: "Mark broken",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          if (selectedMachines) {
            dispatchForSelectedMachines(machineActions.markBroken, {
              message: values.comment,
            });
          }
        }}
        onSuccess={closeSidePanel}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount ?? 0}
        validationSchema={MarkBrokenSchema}
        {...actionProps}
      >
        <MarkBrokenFormFields selectedCount={selectedCount ?? 0} />
      </ActionForm>
    </>
  );
};

export default MarkBrokenForm;
