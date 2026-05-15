import type { ChangeEvent, ReactElement } from "react";

import { Col, Row, Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link, useLocation } from "react-router";
import * as Yup from "yup";

import ActionForm from "@/app/base/components/ActionForm";
import FormikField from "@/app/base/components/FormikField";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

export type OverrideTestFormValues = {
  suppressResults: boolean;
};

const OverrideTestFormSchema = Yup.object().shape({
  suppressResults: Yup.boolean(),
});

type OverrideTestFormProps = {
  isViewingDetails: boolean;
};

export const OverrideTestForm = ({
  isViewingDetails,
}: OverrideTestFormProps): ReactElement => {
  const sendAnalytics = useSendAnalytics();
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

  const isSingleMachine = selectedCount === 1;

  const machineID = isSingleMachine
    ? selectedMachines &&
      "items" in selectedMachines &&
      selectedMachines?.items?.[0]
    : null;

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.OVERRIDE_FAILED_TESTING}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<OverrideTestFormValues, MachineEventErrors>
        actionName={NodeActions.OVERRIDE_FAILED_TESTING}
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{
          suppressResults: false,
        }}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
          label: "Override failed tests",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          const { suppressResults } = values;
          dispatchForSelectedMachines(machineActions.overrideFailedTesting, {
            suppress_failed_script_results: suppressResults,
          });
        }}
        onSuccess={closeSidePanel}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount}
        validationSchema={OverrideTestFormSchema}
        {...actionProps}
      >
        <Row>
          <Col size={12}>
            <>
              <p className="u-sv1">
                Overriding will allow the machines to be deployed, marked with a
                warning.
              </p>
              <FormikField
                label={
                  <span>
                    Suppress test-failure icons in the machines list. Results
                    remain visible in
                    <br />
                    {machineID ? (
                      <Link
                        to={urls.machines.machine.index({
                          id: machineID,
                        })}
                      >
                        Machine &gt; Hardware tests
                      </Link>
                    ) : (
                      "Machine > Hardware tests"
                    )}
                    .
                  </span>
                }
                name="suppressResults"
                onChangeCapture={(e: ChangeEvent<HTMLInputElement>) => {
                  sendAnalytics(
                    `Machine ${isViewingDetails ? "details" : "list"} action form`,
                    "Suppress failed tests",
                    e.target.checked ? "Check" : "Uncheck"
                  );
                }}
                type="checkbox"
              />
            </>
          </Col>
        </Row>
      </ActionForm>
    </>
  );
};

export default OverrideTestForm;
