import type { ReactElement } from "react";
import { useEffect, useState } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import CloneFormFields from "./CloneFormFields";
import CloneResults from "./CloneResults";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { SetSearchFilter } from "@/app/base/types";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine, MachineDetails } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

import "./_index.scss";

type CloneMachineProps = {
  isViewingDetails: boolean;
  searchFilter?: string;
  setSearchFilter?: SetSearchFilter;
};

export type CloneFormValues = {
  interfaces: boolean;
  source: Machine["system_id"];
  storage: boolean;
};

const CloneFormSchema = Yup.object()
  .shape({
    interfaces: Yup.boolean(),
    source: Yup.string().required("Source machine must be selected."),
    storage: Yup.boolean(),
  })
  .test(
    "networkOrStorage",
    "Neither network nor storage selected",
    (values, context) => {
      if (!(values.interfaces || values.storage)) {
        return context.createError({
          message: "Either networking or storage must be selected.",
          path: "hidden", // we don't surface the error at a particular field
        });
      }
      return true;
    }
  )
  .defined();

export const CloneForm = ({
  isViewingDetails,
  searchFilter,
  setSearchFilter,
}: CloneMachineProps): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();

  const selectedMachines = useSelector(machineSelectors.selected);
  const { selectedCount, selectedCountLoading } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter ?? "")
  );

  const {
    dispatch: dispatchForSelectedMachines,
    actionStatus,
    actionErrors,
    ...actionProps
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });
  const [selectedMachine, setSelectedMachine] = useState<MachineDetails | null>(
    null
  );
  const [showResults, setShowResults] = useState(false);

  // Run cleanup function here rather than in the ActionForm otherwise errors
  // get cleared before the results are shown.
  useEffect(() => {
    return () => {
      dispatch(machineActions.cleanup());
    };
  }, [dispatch]);

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.CLONE}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      {showResults || actionErrors ? (
        <CloneResults
          closeForm={closeSidePanel}
          selectedCount={selectedCount}
          setSearchFilter={setSearchFilter}
          sourceMachine={selectedMachine}
          viewingDetails={isViewingDetails}
        />
      ) : (
        <ActionForm<CloneFormValues>
          actionName={NodeActions.CLONE}
          buttonsHelp={
            <p>
              The clone function allows you to apply storage and/or network
              interface configuration from the source machine to selected
              destination machines.{" "}
              <ExternalLink to="https://discourse.maas.io/t/cloning-ui/4855">
                Find out more
              </ExternalLink>
            </p>
          }
          className="clone-form"
          initialValues={{
            interfaces: false,
            source: "",
            storage: false,
          }}
          modelName="machine"
          onCancel={closeSidePanel}
          onSaveAnalytics={{
            action: "Submit",
            category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
            label: "Clone",
          }}
          onSubmit={(values) => {
            dispatch(machineActions.cleanup());
            if (selectedMachines) {
              dispatchForSelectedMachines(machineActions.clone, {
                interfaces: values.interfaces,
                storage: values.storage,
                system_id: values.source,
              });
            }
          }}
          onSuccess={() => {
            setShowResults(true);
          }}
          processingCount={actionStatus === "loading" ? selectedCount : 0}
          selectedCount={selectedCount}
          validationSchema={CloneFormSchema}
          {...actionProps}
        >
          <CloneFormFields
            selectedMachine={selectedMachine}
            setSelectedMachine={setSelectedMachine}
          />
        </ActionForm>
      )}
    </>
  );
};

export default CloneForm;
