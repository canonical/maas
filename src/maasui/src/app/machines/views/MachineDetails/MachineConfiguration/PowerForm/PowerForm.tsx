import { useCallback, useEffect, useState } from "react";

import { Spinner } from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import type { SchemaOf } from "yup";
import * as Yup from "yup";

import PowerFormFields from "./PowerFormFields";

import EditableSection from "@/app/base/components/EditableSection";
import FormikForm from "@/app/base/components/FormikForm";
import NodePowerParameters from "@/app/base/components/node/NodePowerParameters";
import { useCanEdit } from "@/app/base/hooks";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import type { PowerType } from "@/app/store/general/types";
import {
  formatPowerParameters,
  generatePowerParametersSchema,
  getPowerTypeFromName,
  useInitialPowerParameters,
} from "@/app/store/general/utils";
import { machineActions } from "@/app/store/machine";
import machineSelectors from "@/app/store/machine/selectors";
import type { Machine } from "@/app/store/machine/types";
import {
  getMachineFieldScopes,
  isMachineDetails,
} from "@/app/store/machine/utils";
import type { RootState } from "@/app/store/root/types";
import type { PowerParameters as PowerParametersType } from "@/app/store/types/node";

export type PowerFormValues = {
  powerType: Machine["power_type"];
  powerParameters: PowerParametersType;
};

type Props = { systemId: Machine["system_id"] };

const PowerForm = ({ systemId }: Props): React.ReactElement | null => {
  const dispatch = useDispatch();
  const machine = useSelector((state: RootState) =>
    machineSelectors.getById(state, systemId)
  );
  const errors = useSelector(machineSelectors.errors);
  const saved = useSelector(machineSelectors.saved);
  const saving = useSelector(machineSelectors.saving);
  const powerTypes = useSelector(powerTypesSelectors.get);
  const powerTypesLoading = useSelector(powerTypesSelectors.loading);
  const cleanup = useCallback(() => machineActions.cleanup(), []);
  const canEdit = useCanEdit(machine, true);
  const [selectedPowerType, setSelectedPowerType] = useState<PowerType | null>(
    null
  );
  const isDetails = isMachineDetails(machine);
  const initialPowerParameters = useInitialPowerParameters(
    (isDetails && machine.power_parameters) || {}
  );

  useEffect(() => {
    // We set the selected power type outside the scope of the form as its used
    // to generate the form's validation schema.
    if (machine?.power_type) {
      const powerType = getPowerTypeFromName(powerTypes, machine.power_type);
      setSelectedPowerType(powerType);
    }
  }, [machine?.power_type, powerTypes]);

  if (!isDetails || powerTypesLoading) {
    return <Spinner text="Loading..." />;
  }

  const fieldScopes = getMachineFieldScopes(machine);
  const powerParametersSchema = generatePowerParametersSchema(
    selectedPowerType,
    fieldScopes
  );
  const PowerFormSchema: SchemaOf<PowerFormValues> = Yup.object()
    .shape({
      powerParameters: Yup.object().shape(powerParametersSchema),
      powerType: Yup.string().required("Power type is required"),
    })
    .defined();

  return (
    <EditableSection
      canEdit={canEdit}
      hasSidebarTitle
      renderContent={(editing, setEditing) =>
        editing ? (
          <FormikForm<PowerFormValues>
            allowAllEmpty
            allowUnchanged
            cleanup={cleanup}
            editable={editing}
            errors={errors}
            initialValues={{
              powerType: machine.power_type ?? "",
              powerParameters: initialPowerParameters,
            }}
            onCancel={() => {
              setEditing(false);
            }}
            onSaveAnalytics={{
              action: "Configure power",
              category: "Machine details",
              label: "Save changes",
            }}
            onSubmit={(values) => {
              const params = {
                extra_macs: machine.extra_macs,
                power_parameters: formatPowerParameters(
                  selectedPowerType,
                  values.powerParameters,
                  fieldScopes
                ),
                power_type: values.powerType,
                pxe_mac: machine.pxe_mac,
                system_id: machine.system_id,
              };
              dispatch(machineActions.update(params));
            }}
            onSuccess={() => {
              setEditing(false);
            }}
            onValuesChanged={(values) => {
              const powerType = getPowerTypeFromName(
                powerTypes,
                values.powerType
              );
              setSelectedPowerType(powerType);
            }}
            saved={saved}
            saving={saving}
            submitLabel="Save changes"
            validationSchema={PowerFormSchema}
          >
            <PowerFormFields machine={machine} />
          </FormikForm>
        ) : (
          <NodePowerParameters node={machine} />
        )
      }
      title="Power configuration"
    />
  );
};

export default PowerForm;
