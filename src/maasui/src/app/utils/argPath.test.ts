import { argPath } from "./argPath";

describe("argPath", () => {
  it("can handle a URL parameter", () => {
    const urls = {
      machine: argPath<{ id: number }>("/machine/:id"),
    };
    expect(urls.machine({ id: 99 })).toBe("/machine/99");
  });

  it("can get the unmodified URL with parameters", () => {
    const urls = {
      machine: argPath<{ id: number }>("/machine/:id"),
    };
    expect(urls.machine(null)).toBe("/machine/:id");
  });
});
