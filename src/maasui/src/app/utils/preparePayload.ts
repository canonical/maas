/**
 * Clean up the form values to send as an API payload.
 * @param payload - An object of payload values.
 * @param validEmpty - A list of keys for values that should not be removed even
 *                     if they are empty.
 * @param removeAdditional
 * @returns
 */
export const preparePayload = <P extends object, K extends keyof P>(
  payload: P,
  validEmpty: K[] = [],
  removeAdditional: K[] = [],
  removeNull = false
): P => {
  Object.entries(payload).forEach(([key, value]) => {
    if (
      !validEmpty.includes(key as K) &&
      // Remove empty fields or entries that should always be removed.
      (value === "" ||
        value === undefined ||
        (removeNull && value === null) ||
        removeAdditional.includes(key as K))
    ) {
      delete payload[key as K];
    }
  });
  return payload;
};
