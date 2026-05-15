import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { useIsDHCPEnabled, useCanBeDeleted } from "./hooks";

import * as factory from "@/testing/factories";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("useCanBeDeleted", () => {
  it("can be deleted if DHCP is disabled and the subnet has no ips", () => {
    const vlan = factory.vlan({ dhcp_on: false });
    const subnet = factory.subnetDetails({
      ip_addresses: [],
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useCanBeDeleted(subnet.id), {
      wrapper: generateWrapper(store),
    });
    expect(result.current).toBe(true);
  });

  it("cannot be deleted if DHCP is enabled", () => {
    const vlan = factory.vlan({ dhcp_on: true });
    const subnet = factory.subnetDetails({
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useCanBeDeleted(subnet.id), {
      wrapper: generateWrapper(store),
    });
    expect(result.current).toBe(true);
  });

  it("cannot be deleted if DHCP is disabled but the subnet has ips", () => {
    const vlan = factory.vlan({ dhcp_on: false });
    const subnet = factory.subnetDetails({
      ip_addresses: [factory.subnetIP()],
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useCanBeDeleted(subnet.id), {
      wrapper: generateWrapper(store),
    });
    expect(result.current).toBe(true);
  });
});

describe("useIsDHCPEnabled", () => {
  it("is enabled if the subnet's VLAN has DHCP turned on", () => {
    const vlan = factory.vlan({ dhcp_on: true });
    const subnet = factory.subnetDetails({
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useIsDHCPEnabled(subnet.id), {
      wrapper: generateWrapper(store),
    });
    expect(result.current).toBe(true);
  });

  it("is disabled if the subnet's VLAN has DHCP turned off", () => {
    const vlan = factory.vlan({ dhcp_on: false });
    const subnet = factory.subnetDetails({
      vlan: vlan.id,
    });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [subnet],
      }),
      vlan: factory.vlanState({
        items: [vlan],
      }),
    });
    const store = mockStore(state);
    const { result } = renderHook(() => useIsDHCPEnabled(subnet.id), {
      wrapper: generateWrapper(store),
    });
    expect(result.current).toBe(false);
  });
});
