import { getObjectValue, getObjectString } from "./utils";

describe("utils", () => {
  describe("getObjectValue", () => {
    it("can get a parameter object", () => {
      const obj = { unknown: { object: { default: "value" } } };
      expect(getObjectValue(obj.unknown, "object")).toStrictEqual({
        default: "value",
      });
    });

    it("can handle parameters that don't exist", () => {
      const obj = { unknown: { object: { default: "value" } } };
      expect(getObjectValue(obj.unknown, "nope")).toBeNull();
    });

    it("can handle parameters of the wrong type", () => {
      const obj = { unknown: true };
      expect(getObjectValue(obj.unknown, "object")).toBeNull();
    });
  });

  describe("getObjectString", () => {
    it("can get a parameter string", () => {
      const obj = { unknown: { object: { default: "value" } } };
      expect(getObjectString(obj.unknown.object, "default")).toBe("value");
    });

    it("can handle parameters that don't exist", () => {
      const obj = { unknown: { object: { default: "value" } } };
      expect(getObjectString(obj.unknown.object, "nope")).toBeNull();
    });

    it("can handle parameters of the wrong type", () => {
      const obj = { unknown: { object: { default: 9 } } };
      expect(getObjectString(obj.unknown.object, "default")).toBeNull();
    });
  });
});
