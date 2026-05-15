import type { OptionHTMLAttributes } from "react";
import { useEffect } from "react";

import type { SelectProps } from "@canonical/react-components";
import { Select } from "@canonical/react-components";
import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useFormikContext } from "formik";

import FormikField from "@/app/base/components/FormikField";
import type { Props as FormikFieldProps } from "@/app/base/components/FormikField/FormikField";
import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";

type FormValues = Record<
  string,
  OptionHTMLAttributes<HTMLOptionElement>["value"]
>;

export type Props<V extends FormValues = FormValues> = FormikFieldProps & {
  name: keyof V;
  options: NonNullable<SelectProps["options"]>;
};

/**
 * Formik values eventually resolve to the correct types but option values are
 * returned as strings until formik updates the types, so force the values to
 * all be strings so that we're comparing the same types.
 */
const makeString = (
  value: OptionHTMLAttributes<HTMLOptionElement>["value"]
): string => {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" && !isNaN(value)) {
    return value.toString();
  }
  return "";
};

const arraysEqual = (
  array1: (number | string)[],
  array2: (number | string)[]
): boolean => {
  if (array1.length !== array2.length) {
    return false;
  }
  const stringArray: string[] = array2.map((value) => makeString(value));
  return !array1.some(
    (item: number | string) => !stringArray.includes(makeString(item))
  );
};

export const DynamicSelect = <V extends FormValues = FormValues>({
  options,
  name,
  ...props
}: Props<V>): React.ReactElement => {
  const { setFieldValue, values } = useFormikContext<V>();
  const currentValue = makeString(values[name]);
  const previousValue = usePrevious(currentValue, false);
  const previousOptions = usePrevious(options, false);

  useEffect(() => {
    // If the options have changed and the current value no longer exists then
    // reset the value to the first option.
    const currentOptionValues = (options || []).map(({ value }) =>
      makeString(value)
    );
    const previousOptionValues = (previousOptions || []).map(({ value }) =>
      makeString(value)
    );
    if (
      previousValue !== currentValue ||
      (currentOptionValues && !previousOptionValues) ||
      !arraysEqual(currentOptionValues, previousOptionValues)
    ) {
      if (!currentOptionValues.includes(currentValue)) {
        setFieldValue(
          name,
          currentOptionValues.length > 0 ? currentOptionValues[0] : "",
          false
        ).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            name,
            "setFieldValue",
            reason as string
          );
        });
      }
    }
  }, [
    name,
    setFieldValue,
    options,
    currentValue,
    previousOptions,
    previousValue,
  ]);

  return (
    <FormikField component={Select} name={name} options={options} {...props} />
  );
};

export default DynamicSelect;
