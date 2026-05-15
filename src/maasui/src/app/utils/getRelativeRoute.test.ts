import { getRelativeRoute } from "./getRelativeRoute";

it("can get a relative route from a base route", () => {
  const urls = {
    index: "/machine/",
    add: "/machine/add",
  };
  expect(getRelativeRoute(urls.add, urls.index)).toBe("add");
});

it("removes slash prefix", () => {
  const urls = {
    index: "/machine",
    add: "/machine/add/new",
  };
  expect(getRelativeRoute(urls.add, urls.index)).toBe("add/new");
});
