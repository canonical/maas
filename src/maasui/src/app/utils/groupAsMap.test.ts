import { groupAsMap } from "./groupAsMap";

describe("groupAsMap", () => {
  it("correctly groups a list of objects by given key getter function", () => {
    const arr = [
      { name: "Alice", age: 25, height: 165 },
      { name: "Bob", age: 40, height: 165 },
      { name: "Chris", age: 25, height: 165 },
    ];
    const groupedByName = groupAsMap(arr, (person) => person.name);
    const groupedByAge = groupAsMap(arr, (person) => person.age);
    const groupedByHeight = groupAsMap(arr, (person) => person.height);

    expect(Array.from(groupedByName)).toEqual([
      ["Alice", [{ name: "Alice", age: 25, height: 165 }]],
      ["Bob", [{ name: "Bob", age: 40, height: 165 }]],
      ["Chris", [{ name: "Chris", age: 25, height: 165 }]],
    ]);
    expect(Array.from(groupedByAge)).toEqual([
      [
        25,
        [
          { name: "Alice", age: 25, height: 165 },
          { name: "Chris", age: 25, height: 165 },
        ],
      ],
      [40, [{ name: "Bob", age: 40, height: 165 }]],
    ]);
    expect(Array.from(groupedByHeight)).toEqual([
      [
        165,
        [
          { name: "Alice", age: 25, height: 165 },
          { name: "Bob", age: 40, height: 165 },
          { name: "Chris", age: 25, height: 165 },
        ],
      ],
    ]);
  });
});
