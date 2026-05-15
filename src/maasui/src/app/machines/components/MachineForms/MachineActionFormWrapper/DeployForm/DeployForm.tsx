import type { ReactElement } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import { useLocation } from "react-router";
import * as Yup from "yup";

import DeployFormFields from "./DeployFormFields";

import ActionForm from "@/app/base/components/ActionForm";
import NodeActionWarning from "@/app/base/components/node/NodeActionWarning";
import { useFetchActions, useSendAnalytics } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { configActions } from "@/app/store/config";
import configSelectors from "@/app/store/config/selectors";
import { generalActions } from "@/app/store/general";
import {
  defaultMinHweKernel as defaultMinHweKernelSelectors,
  osInfo as osInfoSelectors,
} from "@/app/store/general/selectors";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { MachineEventErrors } from "@/app/store/machine/types";
import { FilterMachines } from "@/app/store/machine/utils";
import {
  useMachineSelectedCount,
  useSelectedMachinesActionsDispatch,
} from "@/app/store/machine/utils/hooks";
import { PodType } from "@/app/store/pod/constants";
import { NodeActions } from "@/app/store/types/node";

const DeploySchema = Yup.object().shape({
  oSystem: Yup.string().required("OS is required"),
  release: Yup.string().required("Release is required"),
  kernel: Yup.string(),
  includeUserData: Yup.boolean(),
  enableHwSync: Yup.boolean(),
  ephemeralDeploy: Yup.boolean(),
  vmHostType: Yup.string().oneOf([PodType.LXD, PodType.VIRSH, ""]),
});

export type DeployFormValues = {
  ephemeralDeploy: boolean;
  includeUserData: boolean;
  kernel: string;
  oSystem: string;
  release: string;
  userData?: string;
  vmHostType: string;
  enableHwSync: boolean;
  enableKernelCrashDump: boolean;
};

type DeployFormProps = {
  isViewingDetails: boolean;
};

export const DeployForm = ({
  isViewingDetails,
}: DeployFormProps): ReactElement => {
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
    actionStatus,
    actionErrors,
  } = useSelectedMachinesActionsDispatch({ selectedMachines, searchFilter });
  const defaultMinHweKernel = useSelector(defaultMinHweKernelSelectors.get);
  const { default_osystem, default_release, osystems, releases } =
    useSelector(osInfoSelectors.get) || {};
  const defaultMinHweKernelLoaded = useSelector(
    defaultMinHweKernelSelectors.loaded
  );
  const osInfoLoaded = useSelector(osInfoSelectors.loaded);
  const sendAnalytics = useSendAnalytics();

  const enableKernelCrashDump = useSelector(
    configSelectors.enableKernelCrashDump
  );
  const configLoaded = useSelector(configSelectors.loaded);

  useFetchActions([
    generalActions.fetchDefaultMinHweKernel,
    generalActions.fetchOsInfo,
    configActions.fetch,
  ]);

  if (
    !defaultMinHweKernelLoaded ||
    !osInfoLoaded ||
    !configLoaded ||
    selectedCountLoading
  ) {
    return <Spinner text="Loading..." />;
  }

  // Default OS+release is set in the backend even if the image has not yet been
  // downloaded. The following conditionals check whether the OS+release actually
  // exist in state before setting initial values in the form.
  let initialOS = "";
  let initialRelease = "";
  if (osystems?.some((osChoice) => osChoice[0] === default_osystem)) {
    initialOS = default_osystem || "";
  }
  if (
    releases?.some((releaseChoice) => {
      const split = releaseChoice[0].split("/");
      return split.length > 1 && split[1] === default_release;
    })
  ) {
    initialRelease = default_release || "";
  }

  return (
    <>
      {selectedCount === 0 ? (
        <NodeActionWarning
          action={NodeActions.DEPLOY}
          nodeType="machine"
          selectedCount={selectedCount}
        />
      ) : null}
      <ActionForm<DeployFormValues, MachineEventErrors>
        actionName={NodeActions.DEPLOY}
        actionStatus={actionStatus}
        allowUnchanged={osystems?.length !== 0 && releases?.length !== 0}
        cleanup={machineActions.cleanup}
        errors={actionErrors}
        initialValues={{
          ephemeralDeploy: false,
          oSystem: initialOS,
          release: initialRelease,
          kernel: defaultMinHweKernel || "",
          includeUserData: false,
          userData: "",
          vmHostType: "",
          enableHwSync: false,
          enableKernelCrashDump: enableKernelCrashDump || false,
        }}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: `Machine ${isViewingDetails ? "details" : "list"} action form`,
          label: "Deploy",
        }}
        onSubmit={(values) => {
          dispatch(machineActions.cleanup());
          const hasUserData =
            values.includeUserData && values.userData && values.userData !== "";
          if (hasUserData) {
            sendAnalytics(
              "Machine list deploy form",
              "Has cloud-init config",
              "Cloud-init user data"
            );
          }
          if (selectedMachines) {
            dispatchForSelectedMachines(machineActions.deploy, {
              distro_series: values.release,
              ephemeral_deploy: values.ephemeralDeploy,
              hwe_kernel: values.kernel,
              osystem: values.oSystem,
              enable_kernel_crash_dump: values.enableKernelCrashDump,
              ...(values.enableHwSync && { enable_hw_sync: true }),
              ...(values.vmHostType === PodType.LXD && {
                register_vmhost: true,
              }),
              ...(values.vmHostType === PodType.VIRSH && {
                install_kvm: true,
              }),
              ...(hasUserData && { user_data: values.userData }),
            });
          }
        }}
        onSuccess={closeSidePanel}
        processingCount={actionStatus === "loading" ? selectedCount : 0}
        selectedCount={selectedCount ?? 0}
        showProcessingCount={false}
        validationSchema={DeploySchema}
      >
        <DeployFormFields />
      </ActionForm>
    </>
  );
};

export default DeployForm;
