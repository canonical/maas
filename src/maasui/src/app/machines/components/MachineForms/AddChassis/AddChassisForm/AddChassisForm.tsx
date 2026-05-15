import type { ReactElement } from "react";
import { useState } from "react";

import { ExternalLink } from "@canonical/maas-react-components";
import { Spinner, Strip } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import AddChassisFormFields from "../AddChassisFormFields";

import FormikForm from "@/app/base/components/FormikForm";
import docsUrls from "@/app/base/docsUrls";
import { useFetchActions } from "@/app/base/hooks";
import { useSidePanel } from "@/app/base/side-panel-context";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { generalActions } from "@/app/store/general";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import type { PowerType } from "@/app/store/general/types";
import { PowerFieldScope } from "@/app/store/general/types";
import {
  formatPowerParameters,
  generatePowerParametersSchema,
  useInitialPowerParameters,
} from "@/app/store/general/utils";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";

export const AddChassisForm = (): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();
  const chassisPowerTypes = useSelector(powerTypesSelectors.canProbe);
  const domains = useSelector(domainSelectors.all);
  const domainsLoaded = useSelector(domainSelectors.loaded);
  const machineErrors = useSelector(machineSelectors.errors);
  const machineSaved = useSelector(machineSelectors.saved);
  const machineSaving = useSelector(machineSelectors.saving);
  const powerTypesLoaded = useSelector(powerTypesSelectors.loaded);

  const [powerType, setPowerType] = useState<PowerType | null>(null);
  const [secondarySubmit, setSecondarySubmit] = useState(false);

  useFetchActions([domainActions.fetch, generalActions.fetchPowerTypes]);

  const initialPowerParameters = useInitialPowerParameters({}, true);
  const powerParametersSchema = generatePowerParametersSchema(powerType, [
    PowerFieldScope.BMC,
  ]);
  const AddChassisSchema = Yup.object().shape({
    domain: Yup.string().required("Domain required"),
    power_parameters: Yup.object().shape(powerParametersSchema),
    power_type: Yup.string().required("Power type required"),
  });

  return (
    <>
      {!(domainsLoaded && powerTypesLoaded) ? (
        <Strip shallow>
          <Spinner text="Loading" />
        </Strip>
      ) : (
        <FormikForm
          buttonsHelp={
            <p>
              <ExternalLink to={docsUrls.addNodesViaChassis}>
                Help with adding chassis
              </ExternalLink>
            </p>
          }
          buttonsHelpClassName="u-align--right"
          cleanup={machineActions.cleanup}
          errors={machineErrors}
          initialValues={{
            domain: (domains.length && domains[0].name) || "",
            power_parameters: initialPowerParameters,
            power_type: "",
          }}
          onCancel={closeSidePanel}
          onSaveAnalytics={{
            action: secondarySubmit ? "Save and add another" : "Save",
            category: "Chassis",
            label: "Add chassis form",
          }}
          onSubmit={(values) => {
            const params: Record<string, string> = {
              chassis_type: values.power_type,
              domain: values.domain,
            };
            const powerParams = formatPowerParameters(
              powerType,
              values.power_parameters,
              [PowerFieldScope.BMC],
              true
            );
            Object.entries(powerParams).forEach(([key, value]) => {
              params[key] = value.toString();
            });
            dispatch(machineActions.addChassis(params));
          }}
          onSuccess={() => {
            if (!secondarySubmit) {
              closeSidePanel();
            }
            setSecondarySubmit(false);
          }}
          onValuesChanged={(values) => {
            const powerType = chassisPowerTypes.find(
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
          submitLabel="Save chassis"
          validationSchema={AddChassisSchema}
        >
          <AddChassisFormFields />
        </FormikForm>
      )}
    </>
  );
};

export default AddChassisForm;
