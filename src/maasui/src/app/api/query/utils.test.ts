import { selectItemsCount, selectById } from "./utils";

describe("selectItemsCount", () => {
  it("should return 0 for undefined input", () => {
    const count = selectItemsCount()(undefined);
    expect(count).toBe(0);
  });

  it("should return the correct count for a non-empty array", () => {
    const data = [1, 2, 3, 4, 5];
    const count = selectItemsCount()(data);
    expect(count).toBe(5);
  });

  it("should return 0 for an empty array", () => {
    const data: number[] = [];
    const count = selectItemsCount()(data);
    expect(count).toBe(0);
  });
});

describe("selectById", () => {
  const testData = [
    { id: 1, name: "Item 1" },
    { id: 2, name: "Item 2" },
    { id: 3, name: "Item 3" },
    { id: null, name: "Null ID Item" },
  ];

  it("should return the correct item when given a valid ID", () => {
    const item = selectById(2)(testData);
    expect(item).toEqual({ id: 2, name: "Item 2" });
  });

  it("should return null when given an ID that does not exist", () => {
    const item = selectById(4)(testData);
    expect(item).toBeNull();
  });

  it("should return the correct item when given a null ID", () => {
    const item = selectById(null)(testData);
    expect(item).toEqual({ id: null, name: "Null ID Item" });
  });

  it("should return null when given a null ID and no matching item exists", () => {
    const dataWithoutNullId = testData.filter((item) => item.id !== null);
    const item = selectById(null)(dataWithoutNullId);
    expect(item).toBeNull();
  });
});
