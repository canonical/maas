import { formatSpeedUnits } from "./formatSpeedUnits";

describe("formatSpeedUnits", () => {
  it("correctly formats to Mbps", () => {
    expect(formatSpeedUnits(12)).toStrictEqual("12 Mbps");
  });

  it("correctly formats to Gbps", () => {
    expect(formatSpeedUnits(1234)).toStrictEqual("1 Gbps");
  });

  it("correctly formats to Tbps", () => {
    expect(formatSpeedUnits(1234567)).toStrictEqual("1 Tbps");
  });
});
