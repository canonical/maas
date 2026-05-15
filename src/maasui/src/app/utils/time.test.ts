import MockDate from "mockdate";
import { register, unregister } from "timezone-mock";

import {
  formatUtcDatetime,
  getTimeDistanceString,
  parseUtcDatetime,
} from "./time";

import type { UtcDatetime } from "@/app/store/types/model";

beforeEach(() => {
  MockDate.set("Fri, 18 Nov. 2022 01:01:00");
  register("Etc/GMT+5");
});

afterEach(() => {
  MockDate.reset();
  unregister();
});

describe("getTimeDistanceString", () => {
  it("returns time distance for UTC TimeString in the past", () => {
    expect(
      getTimeDistanceString("Fri, 18 Nov. 2022 01:00:50" as UtcDatetime)
    ).toEqual("less than a minute ago");
  });
  it("returns time distance for UTC TimeString in the future", () => {
    expect(
      getTimeDistanceString("Fri, 18 Nov. 2022 01:01:10" as UtcDatetime)
    ).toEqual("in less than a minute");
  });
});

describe("formatUtcDatetime", () => {
  it("returns UTC date time in a correct format", () => {
    register("Etc/GMT+0");
    expect(
      formatUtcDatetime("Fri, 18 Nov. 2022 01:00:50" as UtcDatetime)
    ).toEqual("Fri, 18 Nov. 2022 01:00:50 (UTC)");
  });
  it("returns UTC date time in UTC regardless of timezone", () => {
    register("Etc/GMT-1");
    expect(
      formatUtcDatetime("Fri, 18 Nov. 2022 03:00:00" as UtcDatetime)
    ).toEqual("Fri, 18 Nov. 2022 03:00:00 (UTC)");
  });
  it("returns Never if no time is provided", () => {
    const inputTimeString = "" as UtcDatetime;
    const expectedOutput = "Never";
    expect(formatUtcDatetime(inputTimeString)).toEqual(expectedOutput);
  });

  it("appends (UTC) to the given time string", () => {
    const inputTimeString = "Fri, 18 Nov. 2022 01:00:50" as UtcDatetime;
    const expectedOutput = "Fri, 18 Nov. 2022 01:00:50 (UTC)";
    expect(formatUtcDatetime(inputTimeString)).toEqual(expectedOutput);
  });
});

describe("parseUtcDatetime", () => {
  it("parses UTC time string into Date object correctly", () => {
    const utcTimeString = "Fri, 18 Nov. 2022 01:00:50" as UtcDatetime;
    const expectedDate = new Date(Date.UTC(2022, 10, 18, 1, 0, 50)); // Fri, 18 Nov. 2022 01:00:50
    const result = parseUtcDatetime(utcTimeString);
    expect(result).toEqual(expectedDate);
  });

  it("handles leap years correctly", () => {
    const utcTimeString = "Mon, 29 Feb. 2016 12:00:00" as UtcDatetime;
    const expectedDate = new Date(Date.UTC(2016, 1, 29, 12, 0, 0)); // Mon, 29 Feb. 2016 12:00:00
    const result = parseUtcDatetime(utcTimeString);
    expect(result).toEqual(expectedDate);
  });
});
