// Convert an array of numbers into range strings,
// e.g [0, 1, 2, 4, 6, 7] => ["0-2", "4", "6-7"]
export const getRanges = (array: (number | string)[]): string[] => {
  // Initially convert everything to ints so that the values don't need to be
  // parsed in all the subsequent comparisons.
  const intArray = array.map((val) =>
    typeof val === "string" ? parseInt(val, 10) : val
  );
  // Sort the values so that contiguous values are next to each other.
  const sortedArray = [...intArray].sort((a, b) => a - b);
  const ranges = [];
  let rangeStart: number;
  let rangeEnd: number;
  for (let i = 0; i < sortedArray.length; i++) {
    rangeStart = sortedArray[i];
    rangeEnd = rangeStart;
    // Keep incrementing rangeEnd while it's a consecutive number.
    while (sortedArray[i + 1] - sortedArray[i] === 1) {
      rangeEnd = sortedArray[i + 1];
      i++;
    }
    ranges.push(
      rangeStart === rangeEnd ? `${rangeStart}` : `${rangeStart}-${rangeEnd}`
    );
  }
  return ranges;
};
