import { isVersionNewer } from "./isVersionNewer";

describe("isVersionNewer", () => {
  it("returns true if the version is newer than the one being compared to", () => {
    expect(isVersionNewer("2.0.0", "1.0.0")).toEqual(true);
    expect(isVersionNewer("2.0", "1.0")).toEqual(true);
    expect(isVersionNewer("2", "1")).toEqual(true);
  });

  it("returns true if the version has a higher minor version number", () => {
    expect(isVersionNewer("1.2.0", "1.1.0")).toEqual(true);
    expect(isVersionNewer("1.2", "1.1")).toEqual(true);
    expect(isVersionNewer("1.10", "1.9")).toEqual(true);
  });

  it("returns true if the version has a higher patch version number", () => {
    expect(isVersionNewer("1.2.3", "1.2.0")).toEqual(true);
    expect(isVersionNewer("1.2.10", "1.2.9")).toEqual(true);
  });

  it("returns false if the versions are equal", () => {
    expect(isVersionNewer("1.2.3", "1.2.3")).toEqual(false);
    expect(isVersionNewer("1.2.0", "1.2")).toEqual(false);
    expect(isVersionNewer("1.0.0", "1")).toEqual(false);
  });
});
