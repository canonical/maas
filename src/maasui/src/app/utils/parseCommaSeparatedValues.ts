export const parseCommaSeparatedValues = (input: string): string[] => {
  return input
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
};
