import { useEffect, isValidElement } from "react";

import { usePrevious } from "@canonical/react-components/dist/hooks";
import { useFormikContext } from "formik";

import type { AnyObject, APIError } from "../types";

import { FormikFieldChangeError } from "@/app/base/components/FormikField/FormikField";
import { simpleObjectEquality } from "@/app/settings/utils";

/**
 * Combines formik validation errors and errors returned from server
 * for use in formik forms.
 * @param errors - The errors object in redux state.
 */
export const useFormikErrors = <V = AnyObject, E = null>(
  errors?: APIError<E>
): void => {
  const { setFieldError, setFieldTouched, values } = useFormikContext<V>();
  const previousErrors = usePrevious(errors);
  useEffect(() => {
    // Only run this effect if the errors have changed.
    if (
      errors &&
      typeof errors === "object" &&
      !isValidElement(errors) &&
      !simpleObjectEquality(errors, previousErrors)
    ) {
      Object.entries(errors).forEach(([field, fieldErrors]) => {
        let errorString: string;
        if (Array.isArray(fieldErrors)) {
          errorString = fieldErrors.join(" ");
        } else {
          errorString = fieldErrors;
        }
        setFieldError(field, errorString);
        setFieldTouched(field, true, false).catch((reason: unknown) => {
          throw new FormikFieldChangeError(
            field,
            "setFieldTouched",
            reason as string
          );
        });
      });
    }
  }, [errors, previousErrors, setFieldError, setFieldTouched, values]);
};

/**
 * Returns whether a formik form should be disabled, given the current state
 * of the form.
 * @param allowAllEmpty - Whether all fields are allowed to be empty.
 * @param allowUnchanged - Whether the form is enabled even when unchanged.
 * @returns Form is disabled.
 */
export const useFormikFormDisabled = <V extends object>({
  allowAllEmpty = false,
  allowUnchanged = false,
}: {
  allowAllEmpty?: boolean;
  allowUnchanged?: boolean;
}): boolean => {
  const { initialValues, errors, values } = useFormikContext<V>();
  // As we delete keys from values below, we don't want to
  // mutate the actual form values
  const newValues = { ...values };
  let hasErrors = false;
  if (errors) {
    hasErrors = isValidElement(errors) || Object.keys(errors).length > 0;
  }
  if (allowAllEmpty) {
    // If all fields are allowed to be empty then remove the empty fields from
    // the values to compare.
    Object.keys(newValues).forEach((key) => {
      if (!newValues[key as keyof V]) {
        delete newValues[key as keyof V];
      }
    });
  }
  if (allowUnchanged) {
    return hasErrors;
  }
  let matchesInitial = false;
  // Now that fields have been removed then make sure there are some fields left
  // to compare.
  if (Object.keys(newValues).length) {
    matchesInitial = simpleObjectEquality(initialValues, newValues);
  }
  return matchesInitial || hasErrors;
};
