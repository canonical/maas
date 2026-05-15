/**
 * Formik values eventually resolve to the correct types so force the number to
 * the correct type in case it hasn't been resolved yet.
 */
export const toFormikNumber = (value?: number | string): number | undefined => {
  if (typeof value === "string") {
    const intValue = parseInt(value, 10);
    // Formik requires number fields to be `undefined` when they have no value.
    return isNaN(intValue) ? undefined : intValue;
  }
  return value;
};
