import { extractPowerType } from "./extractPowerType";

it("can extract a power type from a description", () => {
  expect(extractPowerType("The OpenBMC Power Driver", "openbmc")).toBe(
    "OpenBMC"
  );
});

it("handles no matching power type", () => {
  expect(extractPowerType("Open BMC Power Driver", "openbmc")).toBe("openbmc");
});

it("handles no description", () => {
  expect(extractPowerType(null, "openbmc")).toBe("openbmc");
});
