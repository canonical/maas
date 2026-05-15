import machine from "./selectors";
import { FilterGroupKey } from "./types";

import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import { NodeActions, NodeStatusCode } from "@/app/store/types/node";
import { callId, enableCallIdMocks } from "@/testing/callId-mock";
import * as factory from "@/testing/factories";

enableCallIdMocks();

describe("machine selectors", () => {
  it("can get all items", () => {
    const items = [factory.machine(), factory.machine()];
    const state = factory.rootState({
      machine: factory.machineState({
        items,
      }),
    });
    expect(machine.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        loading: true,
      }),
    });
    expect(machine.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
      }),
    });
    expect(machine.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        saving: true,
      }),
    });
    expect(machine.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        saved: true,
      }),
    });
    expect(machine.saved(state)).toEqual(true);
  });

  it("can get the active machine's system ID", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        active: "abc123",
      }),
    });
    expect(machine.activeID(state)).toEqual("abc123");
  });

  it("can get the active machine", () => {
    const activeMachine = factory.machine();
    const state = factory.rootState({
      machine: factory.machineState({
        active: activeMachine.system_id,
        items: [activeMachine],
      }),
    });
    expect(machine.active(state)).toEqual(activeMachine);
  });

  it("can get the selected machines", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        selected: { items: ["abc123", "def456"] },
      }),
    });
    expect(machine.selected(state)).toStrictEqual({
      items: ["abc123", "def456"],
    });
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        errors: "Data is incorrect",
      }),
    });
    expect(machine.errors(state)).toStrictEqual("Data is incorrect");
  });

  it("can get a machine by id", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items,
      }),
    });
    expect(machine.getById(state, "909")).toStrictEqual(items[1]);
  });

  it("can get machines by status code", () => {
    const items = [
      factory.machine({ status_code: NodeStatusCode.DISK_ERASING }),
      factory.machine({ status_code: NodeStatusCode.BROKEN }),
      factory.machine({ status_code: NodeStatusCode.DISK_ERASING }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        items,
      }),
    });
    expect(
      machine.getByStatusCode(state, NodeStatusCode.DISK_ERASING)
    ).toStrictEqual([items[0], items[2]]);
  });

  it("can get the machine statuses", () => {
    const statuses = factory.machineStatuses();
    const state = factory.rootState({
      machine: factory.machineState({
        statuses,
      }),
    });
    expect(machine.statuses(state)).toStrictEqual(statuses);
  });

  it("can get the statuses for a machine", () => {
    const machineStatuses = factory.machineStatus();
    const state = factory.rootState({
      machine: factory.machineState({
        statuses: factory.machineStatuses({
          abc123: machineStatuses,
        }),
      }),
    });
    expect(machine.getStatuses(state, "abc123")).toStrictEqual(machineStatuses);
  });

  it("can get a status for a machine", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machine({ system_id: "abc123" })],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus({ creatingPhysical: true }),
        }),
      }),
    });
    expect(
      machine.getStatusForMachine(state, "abc123", "creatingPhysical")
    ).toBe(true);
  });

  it("can get machines that are processing", () => {
    const statuses = factory.machineStatuses({
      abc123: factory.machineStatus({ testing: true }),
      def456: factory.machineStatus(),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        statuses,
      }),
    });
    expect(machine.processing(state)).toStrictEqual(["abc123"]);
  });

  it("can get machines that are tagging", () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    const statuses = factory.machineStatuses({
      abc123: factory.machineStatus({ tagging: true }),
      def456: factory.machineStatus(),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: machines,
        statuses,
      }),
    });
    expect(machine.tagging(state)).toStrictEqual([machines[0]]);
  });

  it("can get machines that are untagging", () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    const statuses = factory.machineStatuses({
      abc123: factory.machineStatus({ untagging: true }),
      def456: factory.machineStatus(),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: machines,
        statuses,
      }),
    });
    expect(machine.untagging(state)).toStrictEqual([machines[0]]);
  });

  it("can get machines that are either tagging or untagging", () => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
      factory.machine({ system_id: "ghi789" }),
    ];
    const statuses = factory.machineStatuses({
      abc123: factory.machineStatus({ tagging: true }),
      def456: factory.machineStatus({ untagging: true }),
      ghi789: factory.machineStatus(),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: machines,
        statuses,
      }),
    });
    expect(machine.updatingTags(state)).toStrictEqual([
      machines[0],
      machines[1],
    ]);
  });

  it("can get machines that are saving pools", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const statuses = factory.machineStatuses({
      "808": factory.machineStatus(),
      "909": factory.machineStatus({ settingPool: true }),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items,
        statuses,
      }),
    });
    expect(machine.settingPool(state)).toStrictEqual([items[1]]);
  });

  it("can get machines that are deleting interfaces", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const statuses = factory.machineStatuses({
      "808": factory.machineStatus(),
      "909": factory.machineStatus({ deletingInterface: true }),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items,
        statuses,
      }),
    });
    expect(machine.deletingInterface(state)).toStrictEqual([items[1]]);
  });

  it("can get machines that are linking subnets", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const statuses = factory.machineStatuses({
      "808": factory.machineStatus(),
      "909": factory.machineStatus({ linkingSubnet: true }),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items,
        statuses,
      }),
    });
    expect(machine.linkingSubnet(state)).toStrictEqual([items[1]]);
  });

  it("can get machines that are unlinking subnets", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const statuses = factory.machineStatuses({
      "808": factory.machineStatus(),
      "909": factory.machineStatus({ unlinkingSubnet: true }),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items,
        statuses,
      }),
    });
    expect(machine.unlinkingSubnet(state)).toStrictEqual([items[1]]);
  });

  it("can get machines that are creating physical interfaces", () => {
    const items = [
      factory.machine({ system_id: "808" }),
      factory.machine({ system_id: "909" }),
    ];
    const statuses = factory.machineStatuses({
      "808": factory.machineStatus(),
      "909": factory.machineStatus({ creatingPhysical: true }),
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items,
        statuses,
      }),
    });
    expect(machine.creatingPhysical(state)).toStrictEqual([items[1]]);
  });

  it("can get all event errors", () => {
    const machineEventErrors = [
      factory.machineEventError(),
      factory.machineEventError(),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(machine.eventErrors(state)).toStrictEqual(machineEventErrors);
  });

  it("can get event errors for a machine", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123" }),
      factory.machineEventError(),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(machine.eventErrorsForIds(state, "abc123")).toStrictEqual([
      machineEventErrors[0],
    ]);
  });

  it("can get event errors for a machine and a provided event", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123", event: NodeActions.TAG }),
      factory.machineEventError({ event: NodeActions.TAG }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(machine.eventErrorsForIds(state, "abc123")).toStrictEqual([
      machineEventErrors[0],
    ]);
  });

  it("can get event errors for a machine and no event", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123", event: null }),
      factory.machineEventError({ id: "abc123", event: NodeActions.TAG }),
      factory.machineEventError({ event: null }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(machine.eventErrorsForIds(state, "abc123", null)).toStrictEqual([
      machineEventErrors[0],
    ]);
  });

  it("can get event errors for a machine and multiple events", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123", event: NodeActions.TAG }),
      factory.machineEventError({ id: "abc123", event: NodeActions.UNTAG }),
      factory.machineEventError({ id: "abc123", event: NodeActions.ABORT }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(
      machine.eventErrorsForIds(state, "abc123", [
        NodeActions.TAG,
        NodeActions.UNTAG,
      ])
    ).toStrictEqual([machineEventErrors[0], machineEventErrors[1]]);
  });

  it("can get event errors for multiple machines", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123" }),
      factory.machineEventError({ id: "def456" }),
      factory.machineEventError(),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(
      machine.eventErrorsForIds(state, ["abc123", "def456"])
    ).toStrictEqual([machineEventErrors[0], machineEventErrors[1]]);
  });

  it("can get event errors for multiple machines and a provided event", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123", event: NodeActions.TAG }),
      factory.machineEventError({ id: "def456", event: NodeActions.TAG }),
      factory.machineEventError({ event: NodeActions.TAG }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(
      machine.eventErrorsForIds(state, ["abc123", "def456"], NodeActions.TAG)
    ).toStrictEqual([machineEventErrors[0], machineEventErrors[1]]);
  });

  it("can get event errors for multiple machines and no event", () => {
    const machineEventErrors = [
      factory.machineEventError({ id: "abc123", event: null }),
      factory.machineEventError({ id: "def456", event: null }),
      factory.machineEventError({ id: "abc123", event: NodeActions.TAG }),
      factory.machineEventError({ id: "def456", event: NodeActions.TAG }),
      factory.machineEventError({ event: null }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        eventErrors: machineEventErrors,
      }),
    });
    expect(
      machine.eventErrorsForIds(state, ["abc123", "def456"], null)
    ).toStrictEqual([machineEventErrors[0], machineEventErrors[1]]);
  });

  it("can get machine count", () => {
    const machines = [factory.machine(), factory.machine()];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [...machines, factory.machine()],
        counts: factory.machineStateCounts({
          "mocked-nanoid": factory.machineStateCount({
            count: 2,
            loaded: true,
            loading: false,
          }),
        }),
      }),
    });
    expect(machine.count(state, "mocked-nanoid")).toStrictEqual(2);
    expect(machine.countLoaded(state, "mocked-nanoid")).toStrictEqual(true);
    expect(machine.countLoading(state, "mocked-nanoid")).toStrictEqual(false);
  });

  it("can get machine filters", () => {
    const filters = [factory.machineFilterGroup()];
    const state = factory.rootState({
      machine: factory.machineState({
        filters,
      }),
    });
    expect(machine.filters(state)).toStrictEqual(filters);
  });

  it("can get filters loaded state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        filtersLoaded: true,
      }),
    });
    expect(machine.filtersLoaded(state)).toBe(true);
  });

  it("can get filters loading state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        filtersLoading: true,
      }),
    });
    expect(machine.filtersLoading(state)).toBe(true);
  });

  it("can get machine filter options", () => {
    const options = [{ key: "option1", label: "Option 1" }];
    const state = factory.rootState({
      machine: factory.machineState({
        filters: [
          factory.machineFilterGroup({
            key: FilterGroupKey.AgentName,
            options,
          }),
        ],
      }),
    });
    expect(
      machine.filterOptions(state, FilterGroupKey.AgentName)
    ).toStrictEqual(options);
  });

  it("sorts filter options", () => {
    const options = [
      { key: "option10", label: "Option 10" },
      { key: "anoption", label: "An option" },
      { key: "option1", label: "Option 1" },
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        filters: [
          factory.machineFilterGroup({
            key: FilterGroupKey.AgentName,
            options,
          }),
        ],
      }),
    });
    expect(
      machine.filterOptions(state, FilterGroupKey.AgentName)
    ).toStrictEqual([options[1], options[2], options[0]]);
  });

  it("can get filter options loaded state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        filters: [
          factory.machineFilterGroup({
            key: FilterGroupKey.AgentName,
            loaded: true,
          }),
        ],
      }),
    });
    expect(machine.filterOptionsLoaded(state, FilterGroupKey.AgentName)).toBe(
      true
    );
  });

  it("can get filter options loading state", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        filters: [
          factory.machineFilterGroup({
            key: FilterGroupKey.AgentName,
            loading: true,
          }),
        ],
      }),
    });
    expect(machine.filterOptionsLoading(state, FilterGroupKey.AgentName)).toBe(
      true
    );
  });

  it("can get items in a list", () => {
    const machines = [factory.machine(), factory.machine()];
    const state = factory.rootState({
      machine: factory.machineState({
        items: [...machines, factory.machine()],
        lists: {
          [callId]: factory.machineStateList({
            loading: true,
            groups: [
              factory.machineStateListGroup({
                items: machines.map(({ system_id }) => system_id),
              }),
            ],
          }),
        },
      }),
    });
    expect(machine.list(state, callId)).toStrictEqual(machines);
  });

  it("can get the count for a list", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            count: 5,
          }),
        },
      }),
    });
    expect(machine.listCount(state, callId)).toBe(5);
  });

  it("can get a group in a list", () => {
    const groups = [
      factory.machineStateListGroup({
        name: "admin1",
      }),
      factory.machineStateListGroup({
        name: "admin2",
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            groups,
          }),
        },
      }),
    });
    expect(machine.listGroups(state, callId)).toStrictEqual(groups);
  });

  it("can get all groups in a list", () => {
    const groups = [
      factory.machineStateListGroup({
        name: "admin1",
      }),
      factory.machineStateListGroup({
        name: "admin2",
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            groups,
          }),
        },
      }),
    });
    expect(machine.listGroup(state, callId, "admin2")).toStrictEqual(groups[1]);
  });

  it("can get a nullish group in a list", () => {
    const groups = [
      factory.machineStateListGroup({
        name: "admin1",
      }),
      factory.machineStateListGroup({
        name: "",
      }),
    ];
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            groups,
          }),
        },
      }),
    });
    expect(machine.listGroup(state, callId, "")).toStrictEqual(groups[1]);
  });

  it("can get the loaded state for a list", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            loaded: true,
          }),
        },
      }),
    });
    expect(machine.listLoaded(state, callId)).toBe(true);
  });

  it("can get the loading state for a list", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            loading: true,
          }),
        },
      }),
    });
    expect(machine.listLoading(state, callId)).toBe(true);
  });

  it("can get an interface by id", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const node = factory.machineDetails({
      interfaces: [nic],
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [node],
      }),
    });
    expect(
      machine.getInterfaceById(state, node.system_id, nic.id)
    ).toStrictEqual(nic);
  });

  it("can get an interface by link id", () => {
    const link = factory.networkLink();
    const nic = factory.machineInterface({
      links: [link],
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const node = factory.machineDetails({
      interfaces: [nic],
    });
    const state = factory.rootState({
      machine: factory.machineState({
        items: [node],
      }),
    });
    expect(
      machine.getInterfaceById(state, node.system_id, null, link.id)
    ).toStrictEqual(nic);
  });

  it("can get unused ids for a details request when the id is being used", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            system_id: "abc123",
          }),
          78910: factory.machineStateDetailsItem({
            system_id: "abc123",
          }),
        },
        lists: {
          [callId]: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["abc123", "def456"],
              }),
            ],
          }),
        },
      }),
    });
    expect(machine.unusedIdsInCall(state, callId)).toStrictEqual([]);
  });

  it("can get unused ids for a details request when the id is not being used", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            system_id: "abc123",
          }),
        },
        lists: {
          [callId]: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["def456", "ghi789"],
              }),
            ],
          }),
        },
      }),
    });
    expect(machine.unusedIdsInCall(state, callId)).toStrictEqual(["abc123"]);
  });

  it("can get unused ids for a list request when the ids are being used", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            system_id: "abc123",
          }),
        },
        lists: {
          111213: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["abc123", "def456"],
              }),
            ],
          }),
          78910: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["def456"],
              }),
            ],
          }),
        },
      }),
    });
    expect(machine.unusedIdsInCall(state, "111213")).toStrictEqual([]);
  });

  it("can get unused ids for a list request when the ids are not being used", () => {
    const state = factory.rootState({
      machine: factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            system_id: "abc123",
          }),
        },
        lists: {
          111213: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["def456", "ghi789"],
              }),
            ],
          }),
          78910: factory.machineStateList({
            groups: [
              factory.machineStateListGroup({
                items: ["jkl101112"],
              }),
            ],
          }),
        },
      }),
    });
    expect(machine.unusedIdsInCall(state, "111213")).toStrictEqual([
      "def456",
      "ghi789",
    ]);
  });
});
