import { formatBytes } from "@canonical/maas-react-components";

/**
 *  Convert a size string (e.g. 1 MB) to a number of bytets
 *  @param sizeString - the size string with a unit, e.g. "1 KB"
 */
export const sizeStringToNumber = (sizeString = ""): number | null => {
  try {
    const regex = /(?<value>\d+(\.\d+)?)(?:\s+?)(?<unit>[a-zA-Z]+)/;
    const groups = regex.exec(sizeString)?.groups;
    if (groups) {
      return formatBytes(
        { value: Number(groups.value), unit: groups.unit },
        {
          convertTo: "B",
        }
      ).value;
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(error);
  }

  return null;
};
