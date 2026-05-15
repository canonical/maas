import { getTableStatus } from "./getTableStatus";

it('returns "loading" if both loading and filter are truthy', () => {
  const result = getTableStatus({ isLoading: true, hasFilter: true });
  expect(result).toEqual("loading");
});

it('returns "default" if both loading and filter are truthy', () => {
  const result = getTableStatus({ isLoading: false, hasFilter: false });
  expect(result).toEqual("default");
});
