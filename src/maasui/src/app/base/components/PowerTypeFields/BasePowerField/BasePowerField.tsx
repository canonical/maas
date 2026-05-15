import { Input, Select } from "@canonical/react-components";
import { useFormikContext } from "formik";

import FormikField from "@/app/base/components/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import type { AnyObject } from "@/app/base/types";
import { PowerFieldType } from "@/app/store/general/types";
import type { PowerField } from "@/app/store/general/types";
import type { PowerParameters } from "@/app/store/types/node";

type Props = {
  field: PowerField;
  powerParametersValueName?: string;
};

export const BasePowerField = <V extends AnyObject>({
  field,
  powerParametersValueName = "power_parameters",
}: Props): React.ReactElement => {
  const { setFieldValue, values } = useFormikContext<V>();
  const { choices, field_type, label, name, required } = field;
  const fieldName = `${powerParametersValueName}.${name}`;

  if (field_type === PowerFieldType.MULTIPLE_CHOICE) {
    // If the field is a multiple choice field, we know that its value must be
    // an array of strings.
    const fieldValue = (values[powerParametersValueName] as PowerParameters)[
      name
    ] as string[];
    return (
      <>
        <p data-testid="field-label">{label}</p>
        {choices.map(([checkboxValue, label]) => {
          const checked = fieldValue.includes(checkboxValue);
          const id = `${fieldName}.${checkboxValue}`;
          return (
            <Input
              checked={checked}
              data-testid="multi-choice-checkbox"
              id={id}
              key={id}
              label={label}
              onChange={() => {
                const newFieldValue = checked
                  ? fieldValue.filter((val) => val !== checkboxValue)
                  : [...fieldValue, checkboxValue];
                setFieldValue(fieldName, newFieldValue).catch(
                  (reason: unknown) => {
                    throw new FormikFieldChangeError(
                      fieldName,
                      "setFieldValue",
                      reason as string
                    );
                  }
                );
              }}
              type="checkbox"
              value={checkboxValue}
            />
          );
        })}
      </>
    );
  }
  return (
    <FormikField
      component={field_type === PowerFieldType.CHOICE ? Select : Input}
      key={fieldName}
      label={label}
      name={fieldName}
      options={
        field_type === "choice"
          ? choices.map((choice) => ({
              key: `${name}-${choice[0]}`,
              label: choice[1],
              value: choice[0],
            }))
          : undefined
      }
      required={required}
      type={
        ((field_type === PowerFieldType.STRING ||
          field_type === PowerFieldType.IP_ADDRESS ||
          field_type === PowerFieldType.VIRSH_ADDRESS ||
          field_type === PowerFieldType.LXD_ADDRESS) &&
          "text") ||
        (field_type === PowerFieldType.PASSWORD && "password") ||
        undefined
      }
    />
  );
};

export default BasePowerField;
