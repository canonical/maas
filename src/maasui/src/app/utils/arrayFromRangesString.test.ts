import { arrayFromRangesString } from "./arrayFromRangesString";

describe("arrayFromRangesString", () => {
  it("handles incorrectly formatted range strings", () => {
    expect(arrayFromRangesString("")).toBe(null);
    expect(arrayFromRangesString("a")).toBe(null);
    expect(arrayFromRangesString("1-a")).toBe(null);
    expect(arrayFromRangesString("1,")).toBe(null);
    expect(arrayFromRangesString("1-")).toBe(null);
    expect(arrayFromRangesString("-1")).toBe(null);
  });

  it("correctly converts string of ranges into array of numbers", () => {
    expect(arrayFromRangesString("1")).toStrictEqual([1]);
    expect(arrayFromRangesString("1, 2, 4, 5")).toStrictEqual([1, 2, 4, 5]);
    expect(arrayFromRangesString("0-2")).toStrictEqual([0, 1, 2]);
    expect(arrayFromRangesString("0-2, 6-7")).toStrictEqual([0, 1, 2, 6, 7]);
    expect(arrayFromRangesString("0-2, 4, 6-7, 9-11")).toStrictEqual([
      0, 1, 2, 4, 6, 7, 9, 10, 11,
    ]);
  });
});
