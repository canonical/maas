import { fileContextStore } from "./file-context";

describe("FileContext", () => {
  const fileKey = "file1";

  afterEach(() => {
    fileContextStore.remove(fileKey);
  });

  it("can retrieve a file", () => {
    fileContextStore.add(fileKey, "test file");
    expect(fileContextStore.get(fileKey)).toBe("test file");
  });

  it("can store a file", () => {
    expect(fileContextStore.get(fileKey)).toBeUndefined();
    fileContextStore.add(fileKey, "test file");
    expect(fileContextStore.get(fileKey)).toBe("test file");
  });

  it("can remove a file", () => {
    fileContextStore.add(fileKey, "test file");
    expect(fileContextStore.get(fileKey)).toBe("test file");
    fileContextStore.remove(fileKey);
    expect(fileContextStore.get(fileKey)).toBeUndefined();
  });
});
