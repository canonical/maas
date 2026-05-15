import { kebabToCamelCase } from "./kebabToCamelCase";

describe("kebabToCamelCase", () => {
  it("correctly converts kebab case strings to camel case strings", () => {
    expect(kebabToCamelCase("string")).toEqual("string");
    expect(kebabToCamelCase("my-string")).toEqual("myString");
    expect(kebabToCamelCase("my-long-string")).toEqual("myLongString");
  });
});
