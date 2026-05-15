import { useEffect, type ReactElement } from "react";

import { useDispatch, useSelector } from "react-redux";

import ActionForm from "@/app/base/components/ActionForm";
import TestFormFields from "@/app/base/components/node/TestFormFields";
import {
  TestFormSchema,
  type TestFormValues,
} from "@/app/base/components/node/TestFormFields/TestFormFields";
import type { HardwareType } from "@/app/base/enum";
import { useSidePanel } from "@/app/base/side-panel-context";
import type { ActionStatuses } from "@/app/base/types";
import { controllerActions } from "@/app/store/controller";
import controllerSelectors, {
  statusSelectors,
} from "@/app/store/controller/selectors";
import { ACTIONS } from "@/app/store/controller/slice";
import type { Controller } from "@/app/store/controller/types";
import type { RootState } from "@/app/store/root/types";
import { scriptActions } from "@/app/store/script";
import scriptSelectors from "@/app/store/script/selectors";
import type { Script } from "@/app/store/script/types";
import { getObjectString } from "@/app/store/script/utils";
import { NodeActions } from "@/app/store/types/node";
import { kebabToCamelCase } from "@/app/utils";

type Props = {
  applyConfiguredNetworking?: boolean;
  controllers: Controller["system_id"][];
  hardwareType?: HardwareType;
  isViewingDetails: boolean;
};

const TestControllerForm = ({
  applyConfiguredNetworking,
  controllers,
  hardwareType,
  isViewingDetails,
}: Props): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const errors = useSelector((state: RootState) =>
    controllerSelectors.eventErrorsForControllers(
      state,
      controllers,
      kebabToCamelCase(NodeActions.TEST)
    )
  )[0]?.error;
  const scripts = useSelector(scriptSelectors.testing);
  const scriptsLoaded = useSelector(scriptSelectors.loaded);
  const urlScripts = useSelector(scriptSelectors.testingWithUrl);
  type FormattedScript = Script & {
    displayName: string;
  };
  const actionStatus = ACTIONS.find(({ name }) => name === NodeActions.TEST)
    ?.status as ActionStatuses;
  const processingControllers = useSelector(
    actionStatus ? statusSelectors[actionStatus] : () => []
  );

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

  return (
    <ActionForm<TestFormValues>
      actionName={NodeActions.TEST}
      actionStatus={actionStatus}
      allowUnchanged
      cleanup={controllerActions.cleanup}
      errors={errors}
      initialValues={{
        enableSSH: false,
        scripts: preselected,
        scriptInputs: initialScriptInputs,
      }}
      loaded={scriptsLoaded}
      modelName="controller"
      onCancel={closeSidePanel}
      onSaveAnalytics={{
        action: "Submit",
        category: `Controller ${
          isViewingDetails ? "details" : "list"
        } action form`,
        label: "Test",
      }}
      onSubmit={(values) => {
        dispatch(controllerActions.cleanup());
        const { enableSSH, scripts, scriptInputs } = values;
        controllers.forEach((controller) => {
          dispatch(
            controllerActions.test({
              enable_ssh: enableSSH,
              script_input: scriptInputs,
              system_id: controller,
              testing_scripts: scripts.map((script) => script.name),
            })
          );
        });
      }}
      processingCount={processingControllers.length}
      selectedCount={controllers.length}
      validationSchema={TestFormSchema}
    >
      <TestFormFields
        modelName="controller"
        preselected={preselected}
        scripts={formattedScripts}
      />
    </ActionForm>
  );
};

export default TestControllerForm;
