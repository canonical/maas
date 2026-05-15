import { chunk } from "./chunk";

describe("chunk", () => {
  it("correctly chunks an array", () => {
    expect(chunk([1, 2, 3], 1)).toStrictEqual([[1], [2], [3]]);
    expect(chunk([1, 2, 3, 4], 2)).toStrictEqual([
      [1, 2],
      [3, 4],
    ]);
    expect(chunk([1, 2, 3], 3)).toStrictEqual([[1, 2, 3]]);
  });

  it("can handle uneven chunks", () => {
    expect(chunk([1, 2, 3], 2)).toStrictEqual([[1, 2], [3]]);
    expect(chunk([1, 2, 3, 4], 3)).toStrictEqual([[1, 2, 3], [4]]);
    expect(chunk([1, 2], 3)).toStrictEqual([[1, 2]]);
  });
});
