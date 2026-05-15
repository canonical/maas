import { FetchGroupKey } from "../types/actions";

import { createMachineListGroup } from "./createMachineListGroup";

import { PowerState } from "@/app/store/types/enum";
import {
  FetchNodeStatus,
  NodeStatus,
  NodeStatusCode,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("createMachineListGroup", () => {
  it("creates a group from architecture", () => {
    const architecture = "arm64/generic";
    const groupBy = FetchGroupKey.Architecture;
    const machine = factory.machine({
      architecture,
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: architecture,
      value: architecture,
    });
  });

  it("creates a group from power state", () => {
    const groupBy = FetchGroupKey.PowerState;
    const machine = factory.machine({
      power_state: PowerState.ON,
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "On",
      value: PowerState.ON,
    });
  });

  it("creates a group from domain", () => {
    const groupBy = FetchGroupKey.Domain;
    const machine = factory.machine({
      domain: factory.modelRef({ name: "maas", id: 1 }),
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "maas",
      value: "maas",
    });
  });

  it("creates a group from KVM", () => {
    const groupBy = FetchGroupKey.Pod;
    const machine = factory.machine({
      pod: factory.modelRef({ name: "active-orca", id: 1 }),
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "active-orca",
      value: "active-orca",
    });
  });

  it("creates a group from KVM type", () => {
    const groupBy = FetchGroupKey.PodType;
    const machine = factory.machine({
      power_type: "lxd",
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "lxd",
      value: "lxd",
    });
  });

  it("creates a group from parent", () => {
    const groupBy = FetchGroupKey.Parent;
    const machine = factory.machine({
      parent: "abc123",
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "abc123",
      value: "abc123",
    });
  });

  it("creates a group from zone", () => {
    const groupBy = FetchGroupKey.Zone;
    const machine = factory.machine({
      zone: factory.modelRef({ name: "maas-zone", id: 1 }),
    });

    expect(
      createMachineListGroup({
        groupBy,
        machine,
      })
    ).toStrictEqual({
      name: "maas-zone",
      value: "maas-zone",
    });
  });

  it("creates a group from status", () => {
    Object.entries(NodeStatus).forEach(([key, value]) => {
      const nodeStatusKey = key as keyof typeof NodeStatus;

      expect(
        createMachineListGroup({
          groupBy: FetchGroupKey.Status,
          machine: factory.machine({
            status: NodeStatus[nodeStatusKey],
            status_code: NodeStatusCode[nodeStatusKey],
          }),
        })
      ).toStrictEqual({
        name: value,
        value: FetchNodeStatus[nodeStatusKey],
      });
    });
  });
});
