export const parseNumberId = (id?: number | string | null): number | null => {
  if (!id) {
    return null;
  }
  if (typeof id === "number") {
    return id;
  }
  const intValue = parseInt(id, 10);
  return isNaN(intValue) ? null : intValue;
};
