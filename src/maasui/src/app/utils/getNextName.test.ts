import { getNextName } from "./getNextName";

describe("getNextName", () => {
  it("can get the next name", () => {
    const names = ["vg0"];
    expect(getNextName(names, "vg")).toStrictEqual("vg1");
  });

  it("ignores names with a different prefix", () => {
    const names = ["vg0", "bcache1"];
    expect(getNextName(names, "vg")).toStrictEqual("vg1");
  });

  it("can get the next name when there are no existing items", () => {
    expect(getNextName([], "vg")).toStrictEqual("vg0");
  });

  it("can get the next name when the names are out of order", () => {
    const names = ["vg1", "vg2", "vg0"];
    expect(getNextName(names, "vg")).toStrictEqual("vg3");
  });

  it("can get the name when there are non sequential names", () => {
    const names = ["vg0", "vg2"];
    expect(getNextName(names, "vg")).toStrictEqual("vg3");
  });

  it("can get the next name when there are partial names", () => {
    const names = ["vg0", "vg"];
    expect(getNextName(names, "vg")).toStrictEqual("vg1");
  });

  it("can get the next name when there are partial similar names", () => {
    const names = ["vg0", "vg2vg1"];
    expect(getNextName(names, "vg")).toStrictEqual("vg1");
  });
});
