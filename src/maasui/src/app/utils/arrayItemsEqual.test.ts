import { arrayItemsEqual } from "./arrayItemsEqual";

describe("arrayItemsEqual", () => {
  it("returns whether all items in two arrays are the same", () => {
    // Same children, same order.
    expect(arrayItemsEqual([1, 2], [1, 2])).toBe(true);
    // Same children, different order.
    expect(arrayItemsEqual([1, 2], [2, 1])).toBe(true);
    // Some children the same, but not all
    expect(arrayItemsEqual([1, 2], [1, 2, 3])).toBe(false);
    // Different children, but the same number.
    expect(arrayItemsEqual([1, 2], [3, 4])).toBe(false);
  });
});
