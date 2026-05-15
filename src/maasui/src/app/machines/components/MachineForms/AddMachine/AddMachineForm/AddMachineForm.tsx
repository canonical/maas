import type { ReactElement } from "react";
import { useState } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Spinner, Strip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddMachineFormFields from "../AddMachineFormFields";
import type { AddMachineValues } from "../types";

import { usePools } from "@/app/api/query/pools";
import { useZones } from "@/app/api/query/zones";
import FormikForm from "@/app/base/components/FormikForm";
import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { hostnameValidation, MAC_ADDRESS_REGEX } from "@/app/base/validation";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { generalActions } from "@/app/store/general";
import { PowerTypeNames } from "@/app/store/general/constants";
import {
  architectures as architecturesSelectors,
  defaultMinHweKernel as defaultMinHweKernelSelectors,
  hweKernels as hweKernelsSelectors,
  powerTypes as powerTypesSelectors,
} from "@/app/store/general/selectors";
import type { PowerType } from "@/app/store/general/types";
import {
  formatPowerParameters,
  generatePowerParametersSchema,
  useInitialPowerParameters,
} from "@/app/store/general/utils";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";

export const AddMachineForm = (): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const architectures = useSelector(architecturesSelectors.get);
  const architecturesLoaded = useSelector(architecturesSelectors.loaded);
  const defaultMinHweKernel = useSelector(defaultMinHweKernelSelectors.get);
  const defaultMinHweKernelLoaded = useSelector(
    defaultMinHweKernelSelectors.loaded
  );
  const domains = useSelector(domainSelectors.all);
  const domainsLoaded = useSelector(domainSelectors.loaded);
  const hweKernelsLoaded = useSelector(hweKernelsSelectors.loaded);
  const machineSaved = useSelector(machineSelectors.saved);
  const machineSaving = useSelector(machineSelectors.saving);
  const machineErrors = useSelector(machineSelectors.errors);
  const powerTypes = useSelector(powerTypesSelectors.get);
  const powerTypesLoaded = useSelector(powerTypesSelectors.loaded);
  const resourcePools = usePools();
  const zones = useZones();

  const [powerType, setPowerType] = useState<PowerType | null>(null);
  const [secondarySubmit, setSecondarySubmit] = useState(false);

  // Fetch all data required for the form.
  useFetchActions([
    domainActions.fetch,
    generalActions.fetchArchitectures,
    generalActions.fetchDefaultMinHweKernel,
    generalActions.fetchHweKernels,
    generalActions.fetchPowerTypes,
  ]);

  const initialPowerParameters = useInitialPowerParameters();
  const AddMachineSchema = Yup.object().shape({
    architecture: Yup.string().required("Architecture required"),
    domain: Yup.string().required("Domain required"),
    extra_macs: Yup.array().of(
      Yup.string().matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
    ),
    hostname: hostnameValidation,
    is_dpu: Yup.boolean(),
    min_hwe_kernel: Yup.string(),
    pool: Yup.string().required("Resource pool required"),
    power_parameters: Yup.object().shape(
      generatePowerParametersSchema(powerType)
    ),
    power_type: Yup.string().required("Power type required"),
    pxe_mac: Yup.string()
      .matches(MAC_ADDRESS_REGEX, "Invalid MAC address")
      .when("power_type", {
        is: (power_type: PowerType["name"]) =>
          power_type !== PowerTypeNames.IPMI,
        then: Yup.string().required("At least one MAC address required"),
      }),
    zone: Yup.string().required("Zone required"),
  });
  const allLoaded =
    architecturesLoaded &&
    defaultMinHweKernelLoaded &&
    domainsLoaded &&
    hweKernelsLoaded &&
    powerTypesLoaded &&
    !resourcePools.isPending &&
    !zones.isPending;

  return (
    <>
      {!allLoaded ? (
        <Strip data-testid="loading" shallow>
          <Spinner text="Loading" />
        </Strip>
      ) : (
        <FormikForm<AddMachineValues>
          buttonsHelp={
            <p>
              <ExternalLink to={docsUrls.addMachines}>
                Help with adding machines
              </ExternalLink>
            </p>
          }
          buttonsHelpClassName="u-align--right"
          cleanup={machineActions.cleanup}
          errors={machineErrors}
          initialValues={{
            architecture: (architectures.length && architectures[0]) || "",
            domain: (domains.length && domains[0].name) || "",
            extra_macs: [],
            hostname: "",
            min_hwe_kernel: defaultMinHweKernel || "",
            is_dpu: false,
            pool:
              (resourcePools?.data?.items?.length &&
                resourcePools?.data.items[0].name) ||
              "",
            power_parameters: initialPowerParameters,
            power_type: "",
            pxe_mac: "",
            zone:
              (zones?.data?.items?.length && zones?.data.items[0].name) || "",
          }}
          onCancel={closeSidePanel}
          onSaveAnalytics={{
            action: secondarySubmit ? "Save and add another" : "Save",
            category: "Machine",
            label: "Add machine form",
          }}
          onSubmit={(values) => {
            const params = {
              architecture: values.architecture,
              domain: { name: values.domain },
              extra_macs: values.extra_macs.filter(Boolean),
              hostname: values.hostname,
              is_dpu: values.is_dpu,
              min_hwe_kernel: values.min_hwe_kernel,
              pool: { name: values.pool },
              power_parameters: formatPowerParameters(
                powerType,
                values.power_parameters
              ),
              power_type: values.power_type as PowerType["name"],
              pxe_mac: values.pxe_mac,
              zone: { name: values.zone },
            };
            dispatch(machineActions.create(params));
          }}
          onSuccess={() => {
            if (!secondarySubmit) {
              closeSidePanel();
            }
            setSecondarySubmit(false);
          }}
          onValuesChanged={(values) => {
            const powerType = powerTypes.find(
              (type) => type.name === values.power_type
            );
            if (powerType) {
              setPowerType(powerType);
            }
          }}
          resetOnSave
          saved={machineSaved}
          saving={machineSaving}
          secondarySubmit={(_, { submitForm }) => {
            setSecondarySubmit(true);
            return submitForm();
          }}
          secondarySubmitLabel="Save and add another"
          submitLabel="Save machine"
          validationSchema={AddMachineSchema}
        >
          <AddMachineFormFields saved={machineSaved} />
        </FormikForm>
      )}
    </>
  );
};

export default AddMachineForm;
