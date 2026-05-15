import type { AnyObject } from "@/app/base/types";

// The script parameters are parsed from a JSON object with any shape so we have
// to do a bit more work to be sure we're retrieving valid values.
export const getObjectValue = (parameter: unknown, key: string): unknown => {
  if (parameter && typeof parameter === "object") {
    const obj = parameter as AnyObject;
    return key in obj ? obj[key] : null;
  }
  return null;
};

// Get a parameter from a parameter object that is expected to be a string.
export const getObjectString = (
  parameter: unknown,
  key: string
): string | null => {
  const value = getObjectValue(parameter, key);
  return value && typeof value === "string" ? value : null;
};
