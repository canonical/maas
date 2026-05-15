import { NetworkInterfaceTypes } from "../types/enum";

import device from "./selectors";

import * as factory from "@/testing/factories";

describe("device selectors", () => {
  it("can get all items", () => {
    const items = [factory.device(), factory.device()];
    const state = factory.rootState({
      device: factory.deviceState({
        items,
      }),
    });
    expect(device.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        loading: true,
      }),
    });
    expect(device.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        loaded: true,
      }),
    });
    expect(device.loaded(state)).toEqual(true);
  });

  it("can get a device by id", () => {
    const items = [
      factory.device({ system_id: "808" }),
      factory.device({ system_id: "909" }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        items,
      }),
    });
    expect(device.getById(state, "909")).toStrictEqual(items[1]);
  });

  it("can get a status for a device", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        items: [factory.device({ system_id: "abc123" })],
        statuses: factory.deviceStatuses({
          abc123: factory.deviceStatus({ creatingInterface: true }),
        }),
      }),
    });
    expect(
      device.getStatusForDevice(state, "abc123", "creatingInterface")
    ).toBe(true);
  });

  it("can get event errors for a device", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123" }),
      factory.deviceEventError(),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(device.eventErrorsForDevices(state, "abc123")).toStrictEqual([
      deviceEventErrors[0],
    ]);
  });

  it("can get event errors for a device and a provided event", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123", event: "creatingInterface" }),
      factory.deviceEventError({ event: "creatingInterface" }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(device.eventErrorsForDevices(state, "abc123")).toStrictEqual([
      deviceEventErrors[0],
    ]);
  });

  it("can get event errors for a device and no event", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123", event: null }),
      factory.deviceEventError({ id: "abc123", event: "creatingInterface" }),
      factory.deviceEventError({ event: null }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(device.eventErrorsForDevices(state, "abc123", null)).toStrictEqual([
      deviceEventErrors[0],
    ]);
  });

  it("can get event errors for multiple devices", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123" }),
      factory.deviceEventError({ id: "def456" }),
      factory.deviceEventError(),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(
      device.eventErrorsForDevices(state, ["abc123", "def456"])
    ).toStrictEqual([deviceEventErrors[0], deviceEventErrors[1]]);
  });

  it("can get event errors for multiple devices and a provided event", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123", event: "creatingInterface" }),
      factory.deviceEventError({ id: "def456", event: "creatingInterface" }),
      factory.deviceEventError({ event: "creatingInterface" }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(
      device.eventErrorsForDevices(
        state,
        ["abc123", "def456"],
        "creatingInterface"
      )
    ).toStrictEqual([deviceEventErrors[0], deviceEventErrors[1]]);
  });

  it("can get event errors for multiple devices and no event", () => {
    const deviceEventErrors = [
      factory.deviceEventError({ id: "abc123", event: null }),
      factory.deviceEventError({ id: "def456", event: null }),
      factory.deviceEventError({ id: "abc123", event: "creatingInterface" }),
      factory.deviceEventError({ id: "def456", event: "creatingInterface" }),
      factory.deviceEventError({ event: null }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({
        eventErrors: deviceEventErrors,
      }),
    });
    expect(
      device.eventErrorsForDevices(state, ["abc123", "def456"], null)
    ).toStrictEqual([deviceEventErrors[0], deviceEventErrors[1]]);
  });

  it("can get the active device's system ID", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        active: "abc123",
      }),
    });
    expect(device.activeID(state)).toEqual("abc123");
  });

  it("can get the active device", () => {
    const activeDevice = factory.device();
    const state = factory.rootState({
      device: factory.deviceState({
        active: activeDevice.system_id,
        items: [activeDevice],
      }),
    });
    expect(device.active(state)).toEqual(activeDevice);
  });

  it("can get the selected device's system ID", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        selected: ["abc123"],
      }),
    });
    expect(device.selectedIDs(state)).toStrictEqual(["abc123"]);
  });

  it("can get the selected device", () => {
    const selectedDevice = factory.device();
    const state = factory.rootState({
      device: factory.deviceState({
        selected: [selectedDevice.system_id],
        items: [selectedDevice],
      }),
    });
    expect(device.selected(state)).toStrictEqual([selectedDevice]);
  });

  it("can search devices by their properties", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        items: [
          factory.device({
            hostname: "foo",
            owner: "rob",
          }),
          factory.device({
            hostname: "bar",
            owner: "foodie",
          }),
          factory.device({
            hostname: "foobar",
            owner: "bazza",
          }),
          factory.device({
            hostname: "baz",
            owner: "robert",
            tags: [1],
          }),
        ],
      }),
      tag: factory.tagState({
        items: [factory.tag({ id: 1, name: "echidna" })],
      }),
    });

    // Get all devices with "foo" in any of the properties.
    let results = device.search(state, "foo", []);
    expect(results.length).toEqual(3);
    expect(results[0].hostname).toEqual("foo");
    expect(results[1].owner).toEqual("foodie");
    expect(results[2].hostname).toEqual("foobar");

    // Get all devices with "bar" in the hostname.
    results = device.search(state, "hostname:bar", []);
    expect(results.length).toEqual(2);
    expect(results[0].hostname).toEqual("bar");
    expect(results[1].hostname).toEqual("foobar");

    // Get all devices with "rob" as the owner.
    results = device.search(state, "owner:=rob", []);
    expect(results.length).toEqual(1);
    expect(results[0].owner).toEqual("rob");

    // Get all devices without "baz" in any of the properties.
    results = device.search(state, "!baz", []);
    expect(results.length).toEqual(2);
    expect(results[0].hostname).toEqual("foo");
    expect(results[1].hostname).toEqual("bar");

    // Get all devices without "baz" in any of the properties.
    results = device.search(state, "echidna", []);
    expect(results.length).toEqual(1);
    expect(results[0].hostname).toEqual("baz");
  });

  it("can get an interface by id", () => {
    const nic = factory.deviceInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const node = factory.deviceDetails({
      interfaces: [nic],
    });
    const state = factory.rootState({
      device: factory.deviceState({
        items: [node],
      }),
    });
    expect(
      device.getInterfaceById(state, node.system_id, nic.id)
    ).toStrictEqual(nic);
  });

  it("can get an interface by link id", () => {
    const link = factory.networkLink();
    const nic = factory.deviceInterface({
      links: [link],
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const node = factory.deviceDetails({
      interfaces: [nic],
    });
    const state = factory.rootState({
      device: factory.deviceState({
        items: [node],
      }),
    });
    expect(
      device.getInterfaceById(state, node.system_id, null, link.id)
    ).toStrictEqual(nic);
  });
});
