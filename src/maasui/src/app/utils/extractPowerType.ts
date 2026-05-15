/**
 * Get the formatted power type from a power type description.
 * @param description - A power type description.
 * @param powerType - A power type.
 * @return The formatted power type or the original power type key.
 */
export const extractPowerType = (
  description: string | null,
  powerType: string | null
): string | null => {
  if (!powerType) {
    return null;
  }

  if (!description) {
    return powerType;
  }

  const position = description.toLowerCase().indexOf(powerType.toLowerCase());
  return position === -1
    ? powerType
    : description.substring(position, position + powerType.length);
};
