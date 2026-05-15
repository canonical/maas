import { timeSpanToMinutes, timeSpanToSeconds } from "./timeSpan";

describe("timeSpanToSeconds", () => {
  it("converts a partial timespan string to a number of seconds", () => {
    expect(timeSpanToSeconds("60s")).toEqual(60);
    expect(timeSpanToSeconds("1m")).toEqual(60);
    expect(timeSpanToSeconds("1h")).toEqual(3600);
  });

  it("converts a timespan string in different formats to a number of seconds", () => {
    expect(timeSpanToSeconds("1hour 1minute 1second")).toEqual(3661);
    expect(timeSpanToSeconds("1hours 1minutes 1seconds")).toEqual(3661);
    expect(timeSpanToSeconds("1hs 1ms 1s")).toEqual(3661);
    expect(timeSpanToSeconds("1h1m1s")).toEqual(3661);
  });

  it("returns 0 for a timespan string in an invalid format", () => {
    expect(timeSpanToSeconds("1")).toEqual(0);
    expect(timeSpanToSeconds("s")).toEqual(0);
  });
});

describe("formatTimeSpanStringToMinutes", () => {
  it("converts a partial timespan string to a number of minutes", () => {
    expect(timeSpanToMinutes("1s")).toEqual(0);
    expect(timeSpanToMinutes("59s")).toEqual(0);
    expect(timeSpanToMinutes("60s")).toEqual(1);
  });
});
