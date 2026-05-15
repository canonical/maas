import service from "./selectors";

import * as factory from "@/testing/factories";

it("can get all items", () => {
  const items = [factory.service(), factory.service()];
  const state = factory.rootState({
    service: factory.serviceState({
      items,
    }),
  });
  expect(service.all(state)).toEqual(items);
});

it("can get the loading state", () => {
  const state = factory.rootState({
    service: factory.serviceState({
      loading: true,
    }),
  });
  expect(service.loading(state)).toEqual(true);
});

it("can get the loaded state", () => {
  const state = factory.rootState({
    service: factory.serviceState({
      loaded: true,
    }),
  });
  expect(service.loaded(state)).toEqual(true);
});

it("can get the errors state", () => {
  const state = factory.rootState({
    service: factory.serviceState({
      errors: "Data is incorrect",
    }),
  });
  expect(service.errors(state)).toStrictEqual("Data is incorrect");
});

it("can get a list of services by their IDs", () => {
  const services = [
    factory.service({ id: 0 }),
    factory.service({ id: 1 }),
    factory.service({ id: 2 }),
  ];
  const state = factory.rootState({
    service: factory.serviceState({
      items: services,
    }),
  });
  expect(service.getByIDs(state, [0, 2])).toStrictEqual([
    services[0],
    services[2],
  ]);
});
