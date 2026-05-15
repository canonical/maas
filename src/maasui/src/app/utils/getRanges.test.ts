import { getRanges } from "./getRanges";

describe("getRanges", () => {
  it("correctly groups ranges together", () => {
    expect(getRanges([0, 1, 2, 3])).toEqual(["0-3"]);
    expect(getRanges([0, 1, 3, 4])).toEqual(["0-1", "3-4"]);
    expect(getRanges([0, 2, 3, 4])).toEqual(["0", "2-4"]);
    expect(getRanges([0, 2, 4, 6])).toEqual(["0", "2", "4", "6"]);
  });

  it("can handle arrays that are out of order", () => {
    expect(getRanges([3, 1, 2, 0])).toEqual(["0-3"]);
    expect(getRanges([4, 0, 1, 3])).toEqual(["0-1", "3-4"]);
    expect(getRanges([3, 4, 0, 2])).toEqual(["0", "2-4"]);
    expect(getRanges([6, 4, 2, 0])).toEqual(["0", "2", "4", "6"]);
  });

  it("can handle different types", () => {
    expect(getRanges([3, "1", 2, "0"])).toEqual(["0-3"]);
  });
});
