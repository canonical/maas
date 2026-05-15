import { useEffect } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";

import ActionForm from "@/app/base/components/ActionForm";
import TestFormFields, {
  TestFormSchema,
  type TestFormValues,
} from "@/app/base/components/node/TestFormFields/TestFormFields";
import type { HardwareType } from "@/app/base/enum";
import { useSidePanel } from "@/app/base/side-panel-context";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { scriptActions } from "@/app/store/script";
import scriptSelectors from "@/app/store/script/selectors";
import type { Script } from "@/app/store/script/types";
import { getObjectString } from "@/app/store/script/utils";
import { NodeActions } from "@/app/store/types/node";

type Props = {
  applyConfiguredNetworking?: Script["apply_configured_networking"];
  hardwareType?: HardwareType;
  isViewingDetails: boolean;
};

const TestMachineForm = ({
  applyConfiguredNetworking,
  hardwareType,
  isViewingDetails,
}: Props) => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const scripts = useSelector(scriptSelectors.testing);
  const scriptsLoaded = useSelector(scriptSelectors.loaded);
  const urlScripts = useSelector(scriptSelectors.testingWithUrl);
  type FormattedScript = Script & {
    displayName: string;
  };
  const selectedMachines = useSelector(machineSelectors.selected);
  const searchFilter = FilterMachines.filtersToString(
    FilterMachines.queryStringToFilters(location.search)
  );
  const { selectedCount, selectedCountLoading } = useMachineSelectedCount(
    FilterMachines.parseFetchFilters(searchFilter)
  );
  const {
    dispatch: dispatchForSelectedMachines,
    actionStatus,
    actionErrors,
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });

  const formattedScripts = scripts.map<FormattedScript>((script) => ({
    ...script,
    displayName: `${script.name} (${script.tags.join(", ")})`,
  }));

  let preselected: FormattedScript[] = [];
  if (hardwareType) {
    preselected = formattedScripts.filter(
      (script) => script?.hardware_type === hardwareType
    );
  } else if (applyConfiguredNetworking) {
    preselected = formattedScripts.filter(
      (script) =>
        script?.apply_configured_networking === applyConfiguredNetworking
    );
  } else {
    const formattedScript = formattedScripts.find(
      (script) => script.name === "smartctl-validate"
    );
    if (formattedScript) {
      preselected = [formattedScript];
    }
  }
  const initialScriptInputs = urlScripts.reduce<TestFormValues["scriptInputs"]>(
    (scriptInputs, script) => {
      if (
        !(script.name in scriptInputs) &&
        script.parameters &&
        script.parameters.url
      ) {
        scriptInputs[script.name] = {
          url: getObjectString(script.parameters.url, "default") || "",
        };
      }
      return scriptInputs;
    },
    {}
  );

  useEffect(() => {
    if (!scriptsLoaded) {
      // scripts are fetched via http, so we explicitly check if they're already
      // loaded here.
      dispatch(scriptActions.fetch());
    }
  }, [dispatch, scriptsLoaded]);

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <ActionForm<TestFormValues, MachineEventErrors>
      actionName={NodeActions.TEST}
      actionStatus={actionStatus}
      allowUnchanged
      cleanup={machineActions.cleanup}
      errors={actionErrors}
      initialValues={{
        enableSSH: false,
        scripts: preselected,
        scriptInputs: initialScriptInputs,
      }}
      loaded={scriptsLoaded}
      modelName={"machine"}
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Machine ${
          isViewingDetails ? "details" : "list"
        } action form`,
        label: "Test",
      }}
      onSubmit={(values) => {
        dispatch(machineActions.cleanup());
        const { enableSSH, scripts, scriptInputs } = values;
        dispatchForSelectedMachines(machineActions.test, {
          enable_ssh: enableSSH,
          script_input: scriptInputs,
          testing_scripts: scripts.map((script) => script.name),
        });
      }}
      onSuccess={closeSidePanel}
      selectedCount={selectedCount ?? 0}
      validationSchema={TestFormSchema}
    >
      <TestFormFields
        modelName={"machine"}
        preselected={preselected}
        scripts={formattedScripts}
      />
    </ActionForm>
  );
};

export default TestMachineForm;
