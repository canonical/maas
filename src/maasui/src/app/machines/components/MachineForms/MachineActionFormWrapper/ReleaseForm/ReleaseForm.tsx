import type { ReactElement } from "react";
import { useEffect } from "react";

import { Spinner, Strip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useLocation } from "react-router";
import * as Yup from "yup";

import ReleaseFormFields from "./ReleaseFormFields";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useSidePanel } from "@/app/base/side-panel-context";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { NodeActions } from "@/app/store/types/node";

export type ReleaseFormValues = {
  enableErase: boolean;
  quickErase: boolean;
  secureErase: boolean;
};

const ReleaseSchema = Yup.object().shape({
  enableErase: Yup.boolean(),
  quickErase: Yup.boolean(),
  secureErase: Yup.boolean(),
});

type ReleaseFormProps = {
  isViewingDetails: boolean;
};

export const ReleaseForm = ({
  isViewingDetails,
}: ReleaseFormProps): ReactElement => {
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

  const configLoaded = useSelector(configSelectors.loaded);
  const enableErase = useSelector(configSelectors.enableDiskErasing);
  const quickErase = useSelector(configSelectors.diskEraseWithQuick);
  const secureErase = useSelector(configSelectors.diskEraseWithSecure);

  useEffect(() => {
    dispatch(configActions.fetch());

    return () => {
      dispatch(machineActions.cleanup());
    };
  }, [dispatch]);

  if (selectedCountLoading || !configLoaded) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.RELEASE}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<ReleaseFormValues, MachineEventErrors>
        actionName={NodeActions.RELEASE}
        allowAllEmpty
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{
          enableErase: enableErase || false,
          quickErase: (enableErase && quickErase) || false,
          secureErase: (enableErase && secureErase) || false,
        }}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
          label: "Release machine",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          const { enableErase, quickErase, secureErase } = values;
          if (selectedMachines) {
            dispatchForSelectedMachines(machineActions.release, {
              erase: enableErase,
              quick_erase: enableErase && quickErase,
              secure_erase: enableErase && secureErase,
            });
          }
        }}
        onSuccess={closeSidePanel}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount ?? 0}
        validationSchema={ReleaseSchema}
        {...actionProps}
      >
        <Strip shallow>
          <ReleaseFormFields />
        </Strip>
      </ActionForm>
    </>
  );
};

export default ReleaseForm;
