import type { ReactElement } from "react";

import {
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { Link, useLocation } from "react-router";
import * as Yup from "yup";

import CommissionFormFields from "./CommissionFormFields";
import type { CommissionFormValues, FormattedScript } from "./types";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useFetchActions, useGetURLId } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import urls from "@/app/base/urls";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import {
  MachineMeta,
  type MachineEventErrors,
} from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import { isUnconfiguredPowerType } from "@/app/store/machine/utils/common";
import {
  useFetchMachine,
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { scriptActions } from "@/app/store/script";
import scriptSelectors from "@/app/store/script/selectors";
import type { Script } from "@/app/store/script/types";
import { ScriptName } from "@/app/store/script/types";
import { getObjectString } from "@/app/store/script/utils";
import { NodeActions } from "@/app/store/types/node";
import { simpleSortByKey } from "@/app/utils";

const formatScripts = (scripts: Script[]): FormattedScript[] =>
  scripts.map((script) => ({
    ...script,
    displayName: `${script.name} (${script.tags.join(", ")})`,
  }));

const CommissionFormSchema = Yup.object().shape({
  enableSSH: Yup.boolean(),
  commissioningScripts: Yup.array().of(
    Yup.object().shape({
      name: Yup.string().required(),
      displayName: Yup.string(),
      description: Yup.string(),
    })
  ),
  testingScripts: Yup.array().of(
    Yup.object().shape({
      name: Yup.string().required(),
      displayName: Yup.string(),
      description: Yup.string(),
    })
  ),
});

type ScriptInput = Record<string, { url: string }>;

type CommissionFormProps = {
  isViewingDetails: boolean;
};

export const CommissionForm = ({
  isViewingDetails,
}: CommissionFormProps): ReactElement => {
  const id = useGetURLId(MachineMeta.PK);
  const { machine } = useFetchMachine(id);
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
  const scriptsLoaded = useSelector(scriptSelectors.loaded);
  const commissioningScripts = useSelector(scriptSelectors.commissioning);
  const preselectedCommissioningScripts = useSelector(
    scriptSelectors.preselectedCommissioning
  );
  const preselectedCommissioningSorted = preselectedCommissioningScripts.sort(
    simpleSortByKey("name")
  );
  const urlScripts = useSelector(scriptSelectors.testingWithUrl);
  const testingScripts = useSelector(scriptSelectors.testing);

  const testingScript = testingScripts.find(
    (script) => script.name === "smartctl-validate"
  );
  const preselectedTestingScripts = testingScript ? [testingScript] : [];

  const initialScriptInputs = urlScripts.reduce<ScriptInput>(
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

  useFetchActions([scriptActions.fetch]);

  if (selectedCountLoading) {
    return <Spinner text={"Loading..."} />;
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.COMMISSION}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<CommissionFormValues, MachineEventErrors>
        actionName={NodeActions.COMMISSION}
        allowUnchanged
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{
          enableSSH: false,
          skipBMCConfig: false,
          skipNetworking: false,
          skipStorage: false,
          updateFirmware: false,
          configureHBA: false,
          commissioningScripts: preselectedCommissioningSorted,
          testingScripts: preselectedTestingScripts,
          scriptInputs: initialScriptInputs,
        }}
        loaded={scriptsLoaded}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
          label: "Commission",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          const {
            enableSSH,
            skipBMCConfig,
            skipNetworking,
            skipStorage,
            updateFirmware,
            configureHBA,
            commissioningScripts,
            testingScripts,
            scriptInputs,
          } = values;
          const commissioningScriptsParam = commissioningScripts.map(
            (script) => script.name
          );
          if (updateFirmware) {
            commissioningScriptsParam.push(ScriptName.UPDATE_FIRMWARE);
          }
          if (configureHBA) {
            commissioningScriptsParam.push(ScriptName.CONFIGURE_HBA);
          }
          const testingScriptsParam = testingScripts.length
            ? testingScripts.map((script) => script.name)
            : [ScriptName.NONE];
          if (selectedMachines) {
            dispatchForSelectedMachines(machineActions.commission, {
              commissioning_scripts: commissioningScriptsParam,
              enable_ssh: enableSSH,
              script_input: scriptInputs,
              skip_bmc_config: skipBMCConfig,
              skip_networking: skipNetworking,
              skip_storage: skipStorage,
              testing_scripts: testingScriptsParam,
            });
          }
        }}
        onSuccess={closeSidePanel}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount ?? 0}
        validationSchema={CommissionFormSchema}
        {...actionProps}
      >
        {machine && isUnconfiguredPowerType(machine) && (
          <NotificationBanner severity="negative" title="Error">
            Unconfigured power type. Please{" "}
            <Link to={urls.machines.machine.configuration(id ? { id } : null)}>
              configure the power type{" "}
            </Link>
            and try again.
          </NotificationBanner>
        )}
        <CommissionFormFields
          commissioningScripts={formatScripts(commissioningScripts)}
          preselectedCommissioning={formatScripts(
            preselectedCommissioningSorted
          )}
          preselectedTesting={formatScripts(preselectedTestingScripts)}
          testingScripts={formatScripts(testingScripts)}
        />
      </ActionForm>
    </>
  );
};

export default CommissionForm;
