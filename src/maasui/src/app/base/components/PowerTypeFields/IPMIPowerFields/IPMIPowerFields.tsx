import type { ReactNode } from "react";
import { useEffect } from "react";

import { Input } from "@canonical/react-components";
import { useFormikContext } from "formik";

import BasePowerField from "../BasePowerField";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import type { AnyObject } from "@/app/base/types";
import type { PowerField as PowerFieldType } from "@/app/store/general/types";
import type { PowerParameters } from "@/app/store/types/node";

type Props = {
  fields: PowerFieldType[];
  powerParametersValueName?: string;
};

export const WORKAROUNDS_FIELD_NAME = "workaround_flags";

export const NONE_WORKAROUND_VALUE = "";

export const IPMIPowerFields = <V extends AnyObject>({
  fields,
  powerParametersValueName = "power_parameters",
}: Props): React.ReactElement | null => {
  const { setFieldValue, values } = useFormikContext<V>();
  const workaroundsFieldName = `${powerParametersValueName}.${WORKAROUNDS_FIELD_NAME}`;
  const workaroundsFieldValue = (
    values[powerParametersValueName] as PowerParameters
  )[WORKAROUNDS_FIELD_NAME];
  const isMultiChoice = Array.isArray(workaroundsFieldValue);

  // Automatically set workaround flags to "None" value if all choices are
  // unselected.
  useEffect(() => {
    if (isMultiChoice && workaroundsFieldValue.length === 0) {
      setFieldValue(workaroundsFieldName, [NONE_WORKAROUND_VALUE]).catch(
        (reason: unknown) => {
          throw new FormikFieldChangeError(
            workaroundsFieldName,
            "setFieldValue",
            reason as string
          );
        }
      );
    }
  }, [
    isMultiChoice,
    setFieldValue,
    workaroundsFieldName,
    workaroundsFieldValue,
  ]);

  return (
    <>
      {fields.reduce<ReactNode[]>((content, field) => {
        const { name, label, choices } = field;
        const isWorkaroundField = name === WORKAROUNDS_FIELD_NAME;

        if (isWorkaroundField && isMultiChoice) {
          content.push(
            <div key={field.name}>
              <p>{label}</p>
              {choices
                // We don't explicitly include the "None" choice, but instead use
                // it as the value only when all other choices are unselected.
                .filter(
                  ([checkboxValue]) => checkboxValue !== NONE_WORKAROUND_VALUE
                )
                .map(([checkboxValue, label]) => {
                  const checked = workaroundsFieldValue.includes(checkboxValue);
                  const id = `${workaroundsFieldName}.${checkboxValue}`;
                  return (
                    <Input
                      checked={checked}
                      id={id}
                      key={id}
                      label={label}
                      onChange={(e) => {
                        const { value } = e.target;
                        const newFieldValue = (
                          workaroundsFieldValue.includes(value)
                            ? workaroundsFieldValue.filter(
                                (val) => val !== checkboxValue
                              )
                            : [...workaroundsFieldValue, checkboxValue]
                        ).filter((val) => val !== NONE_WORKAROUND_VALUE);
                        setFieldValue(
                          workaroundsFieldName,
                          newFieldValue
                        ).catch((reason: unknown) => {
                          throw new FormikFieldChangeError(
                            workaroundsFieldName,
                            "setFieldValue",
                            reason as string
                          );
                        });
                      }}
                      type="checkbox"
                      value={checkboxValue}
                    />
                  );
                })}
            </div>
          );
        } else {
          content.push(
            <BasePowerField
              field={field}
              key={field.name}
              powerParametersValueName={powerParametersValueName}
            />
          );
        }
        return content;
      }, [])}
    </>
  );
};

export default IPMIPowerFields;
