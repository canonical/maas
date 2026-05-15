import reservedIp from "./selectors";

import * as factory from "@/testing/factories";

it("returns list of all reserved IPs", () => {
  const items = [factory.reservedIp(), factory.reservedIp()];
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      items,
    }),
  });
  expect(reservedIp.all(state)).toStrictEqual(items);
});

it("returns reservedip loading state", () => {
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      loading: false,
    }),
  });
  expect(reservedIp.loading(state)).toStrictEqual(false);
});

it("returns reservedip loaded state", () => {
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      loaded: true,
    }),
  });
  expect(reservedIp.loaded(state)).toStrictEqual(true);
});

it("returns reservedip error state", () => {
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      errors: "Unable to list reserved IPs.",
    }),
  });
  expect(reservedIp.errors(state)).toEqual("Unable to list reserved IPs.");
});

it("returns reservedip saving state", () => {
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      saving: true,
    }),
  });
  expect(reservedIp.saving(state)).toStrictEqual(true);
});

it("returns reservedip saved state", () => {
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      saved: true,
    }),
  });
  expect(reservedIp.saved(state)).toStrictEqual(true);
});

it("returns reserved IPs that are in a subnet", () => {
  const subnet = factory.subnet();
  const subnet2 = factory.subnet();
  const items = [
    factory.reservedIp({ subnet: subnet.id }),
    factory.reservedIp({ subnet: subnet.id }),
    factory.reservedIp({ subnet: subnet2.id }),
  ];
  const state = factory.rootState({
    reservedip: factory.reservedIpState({
      items,
    }),
    subnet: factory.subnetState({
      items: [subnet, subnet2],
    }),
  });
  expect(reservedIp.getBySubnet(state, subnet.id)).toStrictEqual(
    items.slice(0, 2)
  );
});

it("handles an undefined subnet", () => {
  const state = factory.rootState();
  expect(reservedIp.getBySubnet(state, undefined)).toStrictEqual([]);
});
