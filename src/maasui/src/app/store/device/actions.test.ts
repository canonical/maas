import { actions } from "./slice";
import { DeviceIpAssignment } from "./types";

import { NodeActions } from "@/app/store/types/node";

describe("device actions", () => {
  it("should handle fetching devices", () => {
    expect(actions.fetch()).toEqual({
      type: "device/fetch",
      meta: {
        model: "device",
        method: "list",
      },
      payload: null,
    });
  });

  it("should handle creating devices", () => {
    expect(
      actions.create({
        interfaces: [
          {
            mac: "aa:bb:cc",
            ip_assignment: DeviceIpAssignment.EXTERNAL,
            ip_address: "1.2.3.4",
            subnet: 9,
          },
        ],
        primary_mac: "aa:bb:cc",
      })
    ).toEqual({
      type: "device/create",
      meta: {
        model: "device",
        method: "create",
      },
      payload: {
        params: {
          interfaces: [
            {
              mac: "aa:bb:cc",
              ip_assignment: DeviceIpAssignment.EXTERNAL,
              ip_address: "1.2.3.4",
              subnet: 9,
            },
          ],
          primary_mac: "aa:bb:cc",
        },
      },
    });
  });

  it("should handle creating an interface", () => {
    expect(
      actions.createInterface({
        enabled: false,
        ip_assignment: DeviceIpAssignment.EXTERNAL,
        mac_address: "aa:bb:cc",
        name: "abc",
        numa_node: 9,
        system_id: "abc123",
      })
    ).toEqual({
      type: "device/createInterface",
      meta: {
        model: "device",
        method: "create_interface",
      },
      payload: {
        params: {
          enabled: false,
          ip_assignment: DeviceIpAssignment.EXTERNAL,
          mac_address: "aa:bb:cc",
          name: "abc",
          numa_node: 9,
          system_id: "abc123",
        },
      },
    });
  });

  it("should handle creating a physical interface", () => {
    expect(
      actions.createPhysical({
        enabled: false,
        ip_assignment: DeviceIpAssignment.EXTERNAL,
        mac_address: "aa:bb:cc",
        name: "abc",
        numa_node: 9,
        system_id: "abc123",
      })
    ).toEqual({
      type: "device/createPhysical",
      meta: {
        model: "device",
        method: "create_physical",
      },
      payload: {
        params: {
          enabled: false,
          ip_assignment: DeviceIpAssignment.EXTERNAL,
          mac_address: "aa:bb:cc",
          name: "abc",
          numa_node: 9,
          system_id: "abc123",
        },
      },
    });
  });

  it("should handle updating devices", () => {
    expect(
      actions.update({
        system_id: "abc123",
        interfaces: [
          {
            mac: "aa:bb:cc",
            ip_assignment: DeviceIpAssignment.EXTERNAL,
            ip_address: "1.2.3.4",
            subnet: 9,
          },
        ],
      })
    ).toEqual({
      type: "device/update",
      meta: {
        model: "device",
        method: "update",
      },
      payload: {
        params: {
          system_id: "abc123",
          interfaces: [
            {
              mac: "aa:bb:cc",
              ip_assignment: DeviceIpAssignment.EXTERNAL,
              ip_address: "1.2.3.4",
              subnet: 9,
            },
          ],
        },
      },
    });
  });

  it("can get a device", () => {
    expect(actions.get("abc123")).toEqual({
      type: "device/get",
      meta: {
        model: "device",
        method: "get",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can set an active device", () => {
    expect(actions.setActive("abc123")).toEqual({
      type: "device/setActive",
      meta: {
        model: "device",
        method: "set_active",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can handle updating an interface", () => {
    expect(
      actions.updateInterface({
        interface_id: 1,
        enabled: true,
        interface_speed: 10,
        link_connected: true,
        link_speed: 100,
        mac_address: "2a:67:d7:a7:0f:f9",
        name: "ech0",
        numa_node: 1,
        tags: ["tag"],
        vlan: 9,
        system_id: "abc123",
      })
    ).toEqual({
      type: "device/updateInterface",
      meta: {
        model: "device",
        method: "update_interface",
      },
      payload: {
        params: {
          interface_id: 1,
          enabled: true,
          interface_speed: 10,
          link_connected: true,
          link_speed: 100,
          mac_address: "2a:67:d7:a7:0f:f9",
          name: "ech0",
          numa_node: 1,
          tags: ["tag"],
          vlan: 9,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle linking a subnet", () => {
    expect(
      actions.linkSubnet({
        interface_id: 1,
        ip_address: "1.2.3.4",
        link_id: 2,
        subnet: 3,
        system_id: "abc123",
      })
    ).toEqual({
      type: "device/linkSubnet",
      meta: {
        model: "device",
        method: "link_subnet",
      },
      payload: {
        params: {
          interface_id: 1,
          ip_address: "1.2.3.4",
          link_id: 2,
          subnet: 3,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle unlinking a subnet", () => {
    expect(
      actions.unlinkSubnet({
        interface_id: 1,
        link_id: 2,
        system_id: "abc123",
      })
    ).toEqual({
      type: "device/unlinkSubnet",
      meta: {
        model: "device",
        method: "unlink_subnet",
      },
      payload: {
        params: {
          interface_id: 1,
          link_id: 2,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle setting the zone", () => {
    expect(actions.setZone({ system_id: "abc123", zone_id: 909 })).toEqual({
      type: "device/setZone",
      meta: {
        model: "device",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_ZONE,
          extra: {
            zone_id: 909,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a device", () => {
    expect(actions.delete({ system_id: "abc123" })).toEqual({
      type: "device/delete",
      meta: {
        model: "device",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.DELETE,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle setting selected devices", () => {
    expect(actions.setSelected(["abc123", "def456"])).toEqual({
      type: "device/setSelected",
      payload: ["abc123", "def456"],
    });
  });
});
