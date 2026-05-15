import { RANGE_REGEX } from "@/app/base/validation";

// Convert a string of ranges into an array of numbers,
// e.g "0-2,4,6-7" => [0, 1, 2, 4, 6, 7]
export const arrayFromRangesString = (
  rangeString?: string
): number[] | null => {
  if (!rangeString?.match(RANGE_REGEX)) {
    return null;
  }
  const rangeArray: number[] = [];
  // Remove whitespace and split string between commas.
  const splitRanges = rangeString?.replace(/\s/g, "").split(",");

  for (const substring of splitRanges) {
    if (/^(\d{1,3}-\d{1,3})$/.exec(substring)) {
      // If the substring is of the form "1-5", add each number in the range.
      const [start, end] = substring
        .split("-")
        .map((str) => Number(str))
        .sort((a, b) => (a > b ? 1 : -1));
      for (let i = start; i <= end; i++) {
        rangeArray.push(i);
      }
    } else if (/^\d{1,3}$/.exec(substring)) {
      // Otherwise, if the substring is just a single number, add it to the range.
      rangeArray.push(Number(substring));
    } else {
      // Otherwise, the string is incorrectly formatted.
      return null;
    }
  }
  return rangeArray;
};
