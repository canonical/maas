import type { ReactNode } from "react";

import { Select, Spinner } from "@canonical/react-components";
import { useFormikContext } from "formik";
import { useSelector } from "react-redux";

import BasePowerField from "./BasePowerField";
import IPMIPowerFields from "./IPMIPowerFields";
import type { LXDPowerFieldsProps } from "./LXDPowerFields";
import LXDPowerFields from "./LXDPowerFields";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { useFetchActions } from "@/app/base/hooks";
import type { AnyObject } from "@/app/base/types";
import { generalActions } from "@/app/store/general";
import { PowerTypeNames } from "@/app/store/general/constants";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import { PowerFieldScope } from "@/app/store/general/types";
import {
  getFieldsInScope,
  getPowerTypeFromName,
} from "@/app/store/general/utils";

type Props = {
  customFieldProps?: {
    [PowerTypeNames.LXD]?: Partial<LXDPowerFieldsProps>;
  };
  disableSelect?: boolean;
  forChassis?: boolean;
  powerParametersValueName?: string;
  powerTypeValueName?: string;
  fieldScopes?: PowerFieldScope[];
  showSelect?: boolean;
};

export const PowerTypeFields = <V extends AnyObject>({
  customFieldProps,
  disableSelect = false,
  forChassis = false,
  powerParametersValueName = "power_parameters",
  powerTypeValueName = "power_type",
  fieldScopes = [PowerFieldScope.BMC, PowerFieldScope.NODE],
  showSelect = true,
}: Props): React.ReactElement => {
  const allPowerTypes = useSelector(powerTypesSelectors.get);
  const chassisPowerTypes = useSelector(powerTypesSelectors.canProbe);
  const powerTypesLoaded = useSelector(powerTypesSelectors.loaded);
  const {
    handleChange,
    initialErrors,
    initialTouched,
    setErrors,
    setFieldValue,
    setTouched,
    values,
  } = useFormikContext<V>();

  useFetchActions([generalActions.fetchPowerTypes]);

  // Only power types that can probe are suitable for use when adding a chassis.
  const powerTypes = forChassis ? chassisPowerTypes : allPowerTypes;

  // Generate field content depending on loading status, custom field content
  // if provided, or on the fields of the selected power type.
  let fieldContent: ReactNode = null;
  const selectedPowerType = powerTypes.find(
    (type) => type.name === values[powerTypeValueName]
  );
  if (!powerTypesLoaded) {
    fieldContent = <Spinner text="Loading..." />;
  } else if (selectedPowerType) {
    const fieldsInScope = getFieldsInScope(selectedPowerType, fieldScopes);
    switch (selectedPowerType.name) {
      case PowerTypeNames.IPMI:
        fieldContent = (
          <IPMIPowerFields
            fields={fieldsInScope}
            powerParametersValueName={powerParametersValueName}
          />
        );
        break;
      case PowerTypeNames.LXD:
        fieldContent = (
          <LXDPowerFields
            fields={fieldsInScope}
            powerParametersValueName={powerParametersValueName}
            {...(customFieldProps?.lxd || {})}
          />
        );
        break;
      default:
        fieldContent = fieldsInScope.map((field) => (
          <BasePowerField
            field={field}
            key={field.name}
            powerParametersValueName={powerParametersValueName}
          />
        ));
    }
  }

  return (
    <>
      {showSelect && (
        <FormikField
          component={Select}
          disabled={!powerTypesLoaded || disableSelect}
          label="Power type"
          name={powerTypeValueName}
          onChange={async (e: React.ChangeEvent<HTMLSelectElement>) => {
            // Reset errors and touched formik state when selecting a new power
            // type, in order to start validation from new.
            // eslint-disable-next-line @typescript-eslint/no-confusing-void-expression
            await handleChange(e);
            setErrors(initialErrors);
            await setTouched(initialTouched);

            const powerType = getPowerTypeFromName(powerTypes, e.target.value);
            // Explicitly set the fields of the selected power type to defaults.
            // This is necessary because some field names are shared across
            // power types (e.g. "power_address"), meaning the value would otherwise
            // persist and appear to be a default value, even though it isn't.
            if (powerType) {
              powerType.fields.forEach((field) => {
                setFieldValue(
                  `${powerParametersValueName}.${field.name}`,
                  field.default || ""
                ).catch((reason: unknown) => {
                  throw new FormikFieldChangeError(
                    `${powerParametersValueName}.${field.name}`,
                    "setFieldValue",
                    reason as string
                  );
                });
              });
            }
          }}
          options={[
            { label: "Select power type", value: "", disabled: true },
            ...powerTypes.map((powerType) => ({
              key: `power-type-${powerType.name}`,
              label: powerType.description,
              value: powerType.name,
            })),
          ]}
          required
        />
      )}
      {fieldContent}
    </>
  );
};

export default PowerTypeFields;
