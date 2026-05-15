import { produce } from "immer";

import { DEFAULT_STATUSES } from "./constants";
import reducers, {
  DEFAULT_COUNT_STATE,
  DEFAULT_LIST_STATE,
  actions,
} from "./slice";
import type { SelectedMachines } from "./types";
import { FilterGroupKey, FilterGroupType } from "./types";
import { FetchGroupKey } from "./types/actions";

import { statusActions } from "@/app/store/status";
import {
  NodeActions,
  NodeStatus,
  NodeStatusCode,
  FetchNodeStatus,
} from "@/app/store/types/node";
import { callId, enableCallIdMocks } from "@/testing/callId-mock";
import * as factory from "@/testing/factories";

enableCallIdMocks();

describe("machine reducer", () => {
  const NOW = 1000;
  beforeEach(() => {
    vi.spyOn(Date, "now").mockImplementation(() => NOW);
  });
  afterEach(() => {
    vi.spyOn(Date, "now").mockRestore();
  });
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      actions: {},
      active: null,
      errors: null,
      counts: {},
      details: {},
      eventErrors: [],
      filters: [],
      filtersLoaded: false,
      filtersLoading: false,
      items: [],
      lists: {},
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
      selected: null,
      statuses: {},
    });
  });

  describe("count", () => {
    it("reduces countError", () => {
      const initialState = factory.machineState({
        counts: {
          [callId]: factory.machineStateCount({
            loading: true,
          }),
        },
      });
      expect(
        reducers(
          initialState,
          actions.countError(callId, "Could not count machines")
        )
      ).toEqual(
        factory.machineState({
          counts: {
            [callId]: factory.machineStateCount({
              errors: "Could not count machines",
              loading: false,
            }),
          },
          eventErrors: [
            factory.machineEventError({
              error: "Could not count machines",
              event: "count",
              id: null,
            }),
          ],
        })
      );
    });

    it("reduces countStart for initial fetch", () => {
      const initialState = factory.machineState({ loading: false });
      expect(reducers(initialState, actions.countStart(callId))).toEqual(
        factory.machineState({
          counts: {
            [callId]: factory.machineStateCount({
              loading: true,
              fetchedAt: NOW,
            }),
          },
        })
      );
    });

    it("reduces countStart for subsequent fetch", () => {
      const initialState = factory.machineState({
        counts: {
          [callId]: {
            ...DEFAULT_COUNT_STATE,
            loading: false,
            fetchedAt: NOW,
          },
        },
      });

      vi.spyOn(Date, "now").mockImplementation(() => NOW + 1);

      const updatedState = reducers(initialState, actions.countStart(callId));

      expect(updatedState.counts[callId]).toEqual({
        ...DEFAULT_COUNT_STATE,
        loading: false,
        refetching: true,
        fetchedAt: expect.any(Number),
        refetchedAt: expect.any(Number),
      });

      expect(updatedState.counts[callId].refetchedAt).toBeGreaterThan(
        initialState.counts[callId].fetchedAt as number
      );
    });

    it("reduces countSuccess", () => {
      const payload = { count: 10 };
      const initialState = factory.machineState({
        counts: {
          [callId]: {
            ...DEFAULT_COUNT_STATE,
            loading: true,
          },
        },
      });

      const updatedState = reducers(
        initialState,
        actions.countSuccess(callId, payload)
      );

      expect(updatedState.counts[callId]).toEqual({
        ...DEFAULT_COUNT_STATE,
        loading: false,
        loaded: true,
        count: payload.count,
      });
    });

    it("ignores calls that don't exist when reducing countSuccess", () => {
      const initialState = factory.machineState({
        counts: {},
      });
      expect(
        reducers(
          initialState,
          actions.countSuccess(callId, {
            count: 11,
          })
        )
      ).toEqual(
        factory.machineState({
          counts: {},
        })
      );
    });
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.machineState({ loading: false });

      expect(reducers(initialState, actions.fetchStart(callId))).toEqual(
        factory.machineState({
          lists: {
            [callId]: factory.machineStateList({
              loading: true,
              fetchedAt: NOW,
            }),
          },
        })
      );
    });

    it("reduces fetchStart for subsequent fetch for the same callId", () => {
      vi.spyOn(Date, "now").mockImplementation(() => NOW + 1);

      const initialState = factory.machineState({
        lists: {
          [callId]: {
            ...DEFAULT_LIST_STATE,
            loading: false,
            fetchedAt: NOW,
          },
        },
      });

      const updatedState = reducers(initialState, actions.fetchStart(callId));

      expect(updatedState.lists[callId]).toEqual(
        expect.objectContaining({
          ...initialState.lists[callId],
          loading: false,
          refetching: true,
          refetchedAt: expect.any(Number),
        })
      );

      expect(updatedState.lists[callId].refetchedAt).toBeGreaterThan(
        initialState.lists[callId].fetchedAt!
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.machineState({
        items: [],
        lists: {
          [callId]: factory.machineStateList({
            loaded: false,
            loading: true,
          }),
        },
        statuses: {},
      });
      const fetchedMachines = [
        factory.machine({ system_id: "abc123" }),
        factory.machine({ system_id: "def456" }),
      ];

      expect(
        reducers(
          initialState,
          actions.fetchSuccess(callId, {
            count: 1,
            cur_page: 2,
            groups: [
              {
                collapsed: true,
                count: 4,
                items: fetchedMachines,
                name: "admin",
                value: "admin1",
              },
            ],
            num_pages: 3,
          })
        )
      ).toEqual(
        factory.machineState({
          items: fetchedMachines,
          lists: {
            [callId]: factory.machineStateList({
              count: 1,
              cur_page: 2,
              groups: [
                factory.machineStateListGroup({
                  collapsed: true,
                  count: 4,
                  items: ["abc123", "def456"],
                  name: "admin",
                  value: "admin1",
                }),
              ],
              num_pages: 3,
              loaded: true,
              loading: false,
            }),
          },
          statuses: {
            abc123: factory.machineStatus(),
            def456: factory.machineStatus(),
          },
        })
      );
    });
  });

  it("reduces invalidateQueries", () => {
    const initialState = factory.machineState({
      loading: false,
      counts: {
        [callId]: factory.machineStateCount({
          loaded: true,
          stale: false,
        }),
      },
      lists: {
        [callId]: factory.machineStateList({
          loaded: true,
          stale: false,
        }),
      },
    });
    expect(reducers(initialState, actions.invalidateQueries())).toEqual(
      factory.machineState({
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: true,
          }),
        },
        lists: {
          [callId]: factory.machineStateList({
            loaded: true,
            stale: true,
          }),
        },
      })
    );
  });

  it("invalidates queries on status/websocketDisconnected", () => {
    const initialState = factory.machineState({
      loading: false,
      counts: {
        [callId]: factory.machineStateCount({
          loaded: true,
          stale: false,
        }),
      },
      lists: {
        [callId]: factory.machineStateList({
          loaded: true,
          stale: false,
        }),
      },
    });
    expect(
      reducers(initialState, statusActions.websocketDisconnected())
    ).toEqual(
      factory.machineState({
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: true,
          }),
        },
        lists: {
          [callId]: factory.machineStateList({
            loaded: true,
            stale: true,
          }),
        },
      })
    );
  });

  describe("updateNotify", () => {
    it("marks filtered machine counts as stale", () => {
      const initialState = factory.machineState({
        loading: false,
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: false,
            params: { filter: { status: FetchNodeStatus.NEW } },
          }),
        },
      });
      expect(
        reducers(initialState, actions.updateNotify(factory.machine()))
      ).toEqual({
        ...initialState,
        counts: { [callId]: { ...initialState.counts[callId], stale: true } },
      });
    });

    it("doesn't mark unfiltered machine counts as stale", () => {
      const initialState = factory.machineState({
        loading: false,
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: false,
          }),
        },
      });
      expect(
        reducers(initialState, actions.updateNotify(factory.machine()))
      ).toEqual(initialState);
    });
  });

  it("marks count requests as stale on delete notify", () => {
    const initialState = factory.machineState({
      loading: false,
      counts: {
        [callId]: factory.machineStateCount({
          loaded: true,
          stale: false,
        }),
      },
    });
    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      factory.machineState({
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: true,
          }),
        },
      })
    );
  });

  it("resets stale status on fetchSuccess", () => {
    const initialState = factory.machineState({
      loading: false,
      lists: {
        [callId]: factory.machineStateList({ loaded: true, stale: true }),
      },
    });
    const groups = [
      { collapsed: true, count: 0, items: [], name: "admin", value: "admin1" },
    ];
    const fetchSuccessPayload = { count: 1, cur_page: 2, groups, num_pages: 3 };
    const expectedState = {
      lists: {
        [callId]: {
          ...factory.machineStateList(),
          ...fetchSuccessPayload,
          loaded: true,
          loading: false,
          stale: false,
        },
      },
    };

    expect(
      reducers(initialState, actions.fetchSuccess(callId, fetchSuccessPayload))
    ).toEqual(factory.machineState(expectedState));
  });

  it("resets stale status on countSuccess", () => {
    const initialState = factory.machineState({
      loading: false,
      counts: {
        [callId]: factory.machineStateCount({
          loaded: true,
          stale: true,
        }),
      },
    });
    expect(
      reducers(initialState, actions.countSuccess(callId, { count: 1 }))
    ).toEqual(
      factory.machineState({
        counts: {
          [callId]: factory.machineStateCount({
            loaded: true,
            stale: false,
            count: 1,
          }),
        },
      })
    );
  });

  it("updates selected machines on delete notify", () => {
    const initialState = factory.machineState({
      selected: { items: ["abc123"] },
    });
    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      factory.machineState({
        selected: { items: [] },
      })
    );
  });

  it("reduces machine action with filter", () => {
    const initialState = factory.machineState();

    expect(
      reducers(
        initialState,
        actions.delete({ filter: { id: "abc123" }, callId: "123456" })
      )
    ).toEqual(initialState);
  });

  it("ignores calls that don't exist when reducing fetchSuccess", () => {
    const initialState = factory.machineState({
      items: [],
      lists: {},
      statuses: {},
    });
    const fetchedMachines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];

    expect(
      reducers(
        initialState,
        actions.fetchSuccess(callId, {
          count: 1,
          cur_page: 2,
          groups: [
            {
              collapsed: true,
              count: 4,
              items: fetchedMachines,
              name: "admin",
              value: "admin1",
            },
          ],
          num_pages: 3,
        })
      )
    ).toEqual(
      factory.machineState({
        items: [],
        lists: {},
        statuses: {},
      })
    );
  });

  it("does not update existing machine details items when reducing fetchSuccess", () => {
    const existingMachine = factory.machineDetails({
      id: 1,
      system_id: "abc123",
    });
    const initialState = factory.machineState({
      items: [existingMachine],
      lists: {
        [callId]: factory.machineStateList(),
      },
      statuses: {
        abc123: factory.machineStatus(),
      },
    });
    const fetchedMachines = [
      factory.machine({ id: 1, system_id: "abc123" }),
      factory.machine({ id: 2, system_id: "def456" }),
    ];

    expect(
      reducers(
        initialState,
        actions.fetchSuccess(callId, {
          count: 1,
          cur_page: 2,
          groups: [
            {
              collapsed: true,
              count: 4,
              items: fetchedMachines,
              name: "admin",
              value: "admin1",
            },
          ],
          num_pages: 3,
        })
      )
    ).toEqual(
      factory.machineState({
        items: [existingMachine, fetchedMachines[1]],
        lists: {
          [callId]: factory.machineStateList({
            count: 1,
            cur_page: 2,
            groups: [
              factory.machineStateListGroup({
                collapsed: true,
                count: 4,
                items: ["abc123", "def456"],
                name: "admin",
                value: "admin1",
              }),
            ],
            num_pages: 3,
            loaded: true,
            loading: false,
          }),
        },
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
      })
    );
  });

  it("updates existing machine items when reducing fetchSuccess", () => {
    const existingMachine = factory.machine({
      id: 1,
      hostname: "old-hostname",
      system_id: "abc123",
    });
    const updatedExistingMachine = {
      ...existingMachine,
      hostname: "updated-hostname",
    };
    const initialState = factory.machineState({
      items: [existingMachine],
      lists: {
        [callId]: factory.machineStateList(),
      },
      statuses: {
        abc123: factory.machineStatus(),
      },
    });
    const fetchedMachines = [
      updatedExistingMachine,
      factory.machine({ id: 2, system_id: "def456" }),
    ];

    expect(
      reducers(
        initialState,
        actions.fetchSuccess(callId, {
          count: 1,
          cur_page: 2,
          groups: [
            {
              collapsed: true,
              count: 4,
              items: fetchedMachines,
              name: "admin",
              value: "admin1",
            },
          ],
          num_pages: 3,
        })
      )
    ).toEqual(
      factory.machineState({
        items: fetchedMachines,
        lists: {
          [callId]: factory.machineStateList({
            count: 1,
            cur_page: 2,
            groups: [
              factory.machineStateListGroup({
                collapsed: true,
                count: 4,
                items: ["abc123", "def456"],
                name: "admin",
                value: "admin1",
              }),
            ],
            num_pages: 3,
            loaded: true,
            loading: false,
          }),
        },
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
      })
    );
  });

  it("reduces fetchError", () => {
    const initialState = factory.machineState({
      lists: {
        [callId]: factory.machineStateList({
          loading: true,
        }),
      },
    });

    expect(
      reducers(
        initialState,
        actions.fetchError(callId, "Could not fetch machines")
      )
    ).toEqual(
      factory.machineState({
        lists: {
          [callId]: factory.machineStateList({
            errors: "Could not fetch machines",
            loading: false,
          }),
        },
        eventErrors: [
          factory.machineEventError({
            error: "Could not fetch machines",
            event: "fetch",
            id: null,
          }),
        ],
      })
    );
  });

  it("reduces filterGroupsStart", () => {
    const initialState = factory.machineState({ filtersLoading: false });

    expect(reducers(initialState, actions.filterGroupsStart())).toEqual(
      factory.machineState({
        filtersLoading: true,
      })
    );
  });

  it("reduces filterGroupsSuccess", () => {
    const initialState = factory.machineState({
      filters: [],
      filtersLoaded: false,
      filtersLoading: true,
    });
    const filterGroup = factory.filterGroup();
    const fetchedGroups = [filterGroup];

    expect(
      reducers(initialState, actions.filterGroupsSuccess(fetchedGroups))
    ).toEqual(
      factory.machineState({
        filters: fetchedGroups,
        filtersLoaded: true,
        filtersLoading: false,
      })
    );
  });

  it("reduces filterGroupsError", () => {
    const initialState = factory.machineState({
      eventErrors: [],
      filtersLoading: true,
    });

    expect(
      reducers(
        initialState,
        actions.filterGroupsError("Could not fetch filter groups")
      )
    ).toEqual(
      factory.machineState({
        errors: "Could not fetch filter groups",
        eventErrors: [
          factory.machineEventError({
            error: "Could not fetch filter groups",
            event: "filterGroups",
            id: null,
          }),
        ],
        filtersLoading: false,
      })
    );
  });

  it("reduces filterOptionsStart", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Owner,
          loading: false,
        }),
      ],
    });
    expect(
      reducers(initialState, actions.filterOptionsStart(FilterGroupKey.Owner))
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Owner,
            loading: true,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsError", () => {
    const initialState = factory.machineState({
      eventErrors: [],
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Owner,
          loading: true,
        }),
      ],
    });
    expect(
      reducers(
        initialState,
        actions.filterOptionsError(
          FilterGroupKey.Owner,
          "Could not fetch filter groups"
        )
      )
    ).toEqual(
      factory.machineState({
        eventErrors: [
          factory.machineEventError({
            error: "Could not fetch filter groups",
            event: "filterOptions",
            id: undefined,
          }),
        ],
        filters: [
          factory.filterGroup({
            errors: "Could not fetch filter groups",
            key: FilterGroupKey.Owner,
            loading: false,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for bool options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.AgentName,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.Bool,
        }),
      ],
    });
    const fetchedOptions = [
      { key: true, label: "On" },
      { key: false, label: "Off" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.AgentName, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.AgentName,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.Bool,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for float options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Mem,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.Float,
        }),
      ],
    });
    const fetchedOptions = [
      { key: 1024.1, label: "1024.1" },
      { key: 1024.2, label: "2024.2" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Mem, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Mem,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.Float,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for lists of float options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Mem,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.FloatList,
        }),
      ],
    });
    const fetchedOptions = [
      { key: 1024.1, label: "1024.1" },
      { key: 1024.2, label: "2024.2" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Mem, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Mem,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.FloatList,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for int options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Status,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.Int,
        }),
      ],
    });
    const fetchedOptions = [
      { key: 1, label: "New" },
      { key: 2, label: "Ready" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Status, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Status,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.Int,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for lists of int options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Status,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.IntList,
        }),
      ],
    });
    const fetchedOptions = [
      { key: 1, label: "New" },
      { key: 2, label: "Ready" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Status, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Status,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.IntList,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for string options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Tags,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.String,
        }),
      ],
    });
    const fetchedOptions = [
      { key: "tag1", label: "Tag 1" },
      { key: "tag2", label: "Tag 2" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Tags, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Tags,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.String,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for dict options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.AgentName,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.Dict,
        }),
      ],
    });
    const fetchedOptions = [
      { key: "iface:name=eth0", label: "name=eth0" },
      { key: "iface:name=eth1", label: "name=eth1" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.AgentName, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.AgentName,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.Dict,
          }),
        ],
      })
    );
  });

  it("reduces filterOptionsSuccess for lists of string options", () => {
    const initialState = factory.machineState({
      filters: [
        factory.filterGroup({
          key: FilterGroupKey.Owner,
          options: null,
          loaded: false,
          loading: true,
          type: FilterGroupType.StringList,
        }),
      ],
    });
    const fetchedOptions = [
      { key: "admin", label: "Admin" },
      { key: "admin2", label: "Admin2" },
    ];
    expect(
      reducers(
        initialState,
        actions.filterOptionsSuccess(FilterGroupKey.Owner, fetchedOptions)
      )
    ).toEqual(
      factory.machineState({
        filters: [
          factory.filterGroup({
            key: FilterGroupKey.Owner,
            options: fetchedOptions,
            loaded: true,
            loading: false,
            type: FilterGroupType.StringList,
          }),
        ],
      })
    );
  });

  it("reduces getStart", () => {
    const initialState = factory.machineState({ loading: false });

    expect(
      reducers(initialState, actions.getStart({ system_id: "abc123" }, callId))
    ).toEqual(
      factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            loading: true,
            system_id: "abc123",
          }),
        },
      })
    );
  });

  it("reduces getError", () => {
    const initialState = factory.machineState({
      details: {
        [callId]: factory.machineStateDetailsItem({
          system_id: "abc123",
        }),
      },
      errors: null,
    });

    expect(
      reducers(
        initialState,
        actions.getError({ system_id: "abc123" }, callId, {
          system_id: "id was not supplied",
        })
      )
    ).toEqual(
      factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            errors: { system_id: "id was not supplied" },
            system_id: "abc123",
          }),
        },
        errors: null,
        eventErrors: [
          factory.machineEventError({
            error: { system_id: "id was not supplied" },
            event: "get",
            id: "abc123",
          }),
        ],
      })
    );
  });

  it("should update if machine exists on getSuccess", () => {
    const initialState = factory.machineState({
      details: {
        [callId]: factory.machineStateDetailsItem({
          loading: true,
          system_id: "abc123",
        }),
      },
      items: [factory.machine({ system_id: "abc123", hostname: "machine1" })],
      statuses: {
        abc123: factory.machineStatus(),
      },
    });
    const updatedMachine = factory.machineDetails({
      system_id: "abc123",
      hostname: "machine1-newname",
    });

    expect(
      reducers(
        initialState,
        actions.getSuccess({ system_id: "abc123" }, callId, updatedMachine)
      )
    ).toEqual(
      factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            loaded: true,
            loading: false,
            system_id: "abc123",
          }),
        },
        items: [updatedMachine],
        loading: false,
        statuses: {
          abc123: factory.machineStatus(),
        },
      })
    );
  });

  it("reduces getSuccess", () => {
    const initialState = factory.machineState({
      details: {
        [callId]: factory.machineStateDetailsItem({
          loading: true,
          system_id: "abc123",
        }),
      },
      items: [factory.machine({ system_id: "abc123" })],
      statuses: {
        abc123: factory.machineStatus(),
      },
    });
    const newMachine = factory.machineDetails({ system_id: "def456" });

    expect(
      reducers(
        initialState,
        actions.getSuccess({ system_id: "abc123" }, callId, newMachine)
      )
    ).toEqual(
      factory.machineState({
        details: {
          [callId]: factory.machineStateDetailsItem({
            loaded: true,
            loading: false,
            system_id: "abc123",
          }),
        },
        items: [...initialState.items, newMachine],
        loading: false,
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
      })
    );
  });

  it("ignores calls that don't exist when reducing getSuccess", () => {
    const initialState = factory.machineState({
      details: {},
      items: [],
      statuses: {},
    });
    const newMachine = factory.machineDetails({ system_id: "def456" });

    expect(
      reducers(
        initialState,
        actions.getSuccess({ system_id: "abc123" }, callId, newMachine)
      )
    ).toEqual(
      factory.machineState({
        details: {},
        items: [],
        statuses: {},
      })
    );
  });

  it("reduces setActiveSuccess", () => {
    const initialState = factory.machineState({ active: null });

    expect(
      reducers(
        initialState,
        actions.setActiveSuccess(
          factory.machineDetails({ system_id: "abc123" })
        )
      )
    ).toEqual(factory.machineState({ active: "abc123" }));
  });

  it("reduces setActiveError", () => {
    const initialState = factory.machineState({
      active: "abc123",
      errors: null,
    });

    expect(
      reducers(initialState, actions.setActiveError("Machine does not exist"))
    ).toEqual(
      factory.machineState({
        active: null,
        errors: "Machine does not exist",
        eventErrors: [
          factory.machineEventError({
            error: "Machine does not exist",
            event: "setActive",
            id: null,
          }),
        ],
      })
    );
  });

  it("reduces createStart", () => {
    const initialState = factory.machineState({ saved: true, saving: false });

    expect(reducers(initialState, actions.createStart())).toEqual(
      factory.machineState({
        saved: false,
        saving: true,
      })
    );
  });

  it("reduces createError", () => {
    const initialState = factory.machineState({
      errors: null,
      saved: false,
      saving: true,
    });

    expect(
      reducers(
        initialState,
        actions.createError({ name: "name already exists" })
      )
    ).toEqual(
      factory.machineState({
        errors: { name: "name already exists" },
        eventErrors: [
          factory.machineEventError({
            error: { name: "name already exists" },
            event: "create",
            id: null,
          }),
        ],
        saved: false,
        saving: false,
      })
    );
  });

  it("reduces deleteNotify", () => {
    const machines = [
      factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
      factory.machine({ id: 2, system_id: "def456", hostname: "node2" }),
    ];
    const initialList = factory.machineStateList({
      count: 20,
      cur_page: 1,
      groups: [
        factory.machineStateListGroup({
          // count can be higher than items.length due to pagination
          count: 15,
          items: ["abc123", "def456"],
        }),
      ],
    });
    const initialState = factory.machineState({
      lists: {
        callId: initialList,
      },
      items: machines,
      selected: { items: ["abc123"] },
      statuses: {
        abc123: factory.machineStatus(),
        def456: factory.machineStatus(),
      },
    });
    const nextState = produce(initialState, (draft) => {
      const list = draft.lists.callId;
      list.count = 19;
      list.groups![0].count = 14;
      list.groups![0].items = ["def456"];
      draft.items = [initialState.items[1]];
      draft.selected = { items: [] };
      delete draft.statuses.abc123;
    });
    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      nextState
    );
  });

  it("reduces deleteNotify when last machine in a group is removed", () => {
    const machines = [
      factory.machine({
        id: 1,
        system_id: "abc123",
        hostname: "node1",
        status: NodeStatus.NEW,
        status_code: NodeStatusCode.NEW,
      }),
      factory.machine({
        id: 2,
        system_id: "def456",
        hostname: "node2",
        status: NodeStatus.FAILED_COMMISSIONING,
        status_code: NodeStatusCode.FAILED_COMMISSIONING,
      }),
    ];
    const newGroup = factory.machineStateListGroup({
      name: "New",
      value: "new",
      items: ["abc123"],
      count: 1,
    });
    const failedCommissioningGroup = factory.machineStateListGroup({
      name: "Failed commissioning",
      value: "failed_commissioning",
      items: ["def456"],
      count: 1,
    });
    const initialState = factory.machineState({
      lists: {
        callId: factory.machineStateList({
          groups: [newGroup, failedCommissioningGroup],
        }),
      },
      items: machines,
      selected: { items: ["def456"] },
      statuses: {
        abc123: factory.machineStatus(),
        def456: factory.machineStatus(),
        ghi789: factory.machineStatus(),
      },
    });
    const nextState = produce(initialState, (draft) => {
      draft.lists.callId.groups = [newGroup];
      draft.items = [initialState.items[0]];
      draft.selected = { items: [] };
      delete draft.statuses.def456;
    });
    expect(reducers(initialState, actions.deleteNotify("def456"))).toEqual(
      nextState
    );
  });

  it("reduces deleteNotify with groups of machines", () => {
    const machines = [
      factory.machine({
        id: 1,
        system_id: "abc123",
        hostname: "node1",
        status: NodeStatus.NEW,
        status_code: NodeStatusCode.NEW,
      }),
      factory.machine({
        id: 3,
        system_id: "def456",
        hostname: "node3",
        status: NodeStatus.NEW,
        status_code: NodeStatusCode.NEW,
      }),
    ];
    const group = factory.machineStateListGroup({
      name: "New",
      value: "new",
      items: ["abc123", "def456"],
      count: 2,
    });
    const initialState = factory.machineState({
      lists: {
        callId: factory.machineStateList({
          count: 2,
          groups: [group],
        }),
      },
      items: machines,
      selected: { items: ["abc123"] },
      statuses: {
        abc123: factory.machineStatus(),
        def456: factory.machineStatus(),
      },
    });
    const nextState = produce(initialState, (draft) => {
      const list = draft.lists.callId;
      list.count = 1;
      list.groups = [{ ...group, count: 1, items: ["def456"] }];
      draft.items = [initialState.items[1]];
      draft.selected = { items: [] };
      delete draft.statuses.abc123;
    });
    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      nextState
    );
  });

  it("reduces updateNotify", () => {
    const machines = [
      factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
      factory.machine({ id: 2, system_id: "def456", hostname: "node2" }),
    ];
    const initialState = factory.machineState({
      lists: {
        [callId]: factory.machineStateList({
          groups: [
            factory.machineStateListGroup({
              items: machines.map((machine) => machine.system_id),
            }),
          ],
        }),
      },
      items: machines,
    });
    const updatedMachine = factory.machine({
      id: 1,
      system_id: "abc123",
      hostname: "node1v2",
    });

    expect(
      reducers(initialState, actions.updateNotify(updatedMachine))
    ).toEqual(
      factory.machineState({
        lists: {
          [callId]: { ...initialState.lists[callId] },
        },
        items: [updatedMachine, initialState.items[1]],
      })
    );
  });

  describe("updateNotify", () => {
    it("reduces updateNotify for machine moved to a group that's not in the current list", () => {
      const abc123 = factory.machine({
        id: 1,
        system_id: "abc123",
        hostname: "node1",
        status: NodeStatus.COMMISSIONING,
      });
      const initialState = factory.machineState({
        items: [
          abc123,
          factory.machine({
            id: 2,
            system_id: "def456",
            hostname: "node2",
            status: NodeStatus.COMMISSIONING,
          }),
        ],
        lists: {
          [callId]: factory.machineStateList({
            count: 2,
            cur_page: 2,
            groups: [
              factory.machineStateListGroup({
                collapsed: false,
                count: 2,
                items: ["abc123", "def456"],
                name: NodeStatus.COMMISSIONING,
                value: FetchNodeStatus.COMMISSIONING,
              }),
            ],
            num_pages: 3,
            loaded: true,
            loading: false,
            params: { group_key: FetchGroupKey.Status },
          }),
        },
      });
      const updatedMachine = factory.machine({
        ...abc123,
        status: NodeStatus.FAILED_COMMISSIONING,
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedMachine))
      ).toEqual(
        factory.machineState({
          items: [updatedMachine, initialState.items[1]],
          lists: {
            [callId]: {
              ...initialState.lists[callId],
              groups: [
                factory.machineStateListGroup({
                  collapsed: false,
                  count: 1,
                  items: ["def456"],
                  name: NodeStatus.COMMISSIONING,
                  value: FetchNodeStatus.COMMISSIONING,
                }),
                factory.machineStateListGroup({
                  collapsed: false,
                  count: null,
                  items: ["abc123"],
                  name: NodeStatus.FAILED_COMMISSIONING,
                  value: FetchNodeStatus.FAILED_COMMISSIONING,
                }),
              ],
            },
          },
        })
      );
    });
  });

  it("reduces checkPowerError", () => {
    const machines = [
      factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
    ];
    const initialState = factory.machineState({
      items: machines,
      statuses: { abc123: factory.machineStatus({ checkingPower: true }) },
    });

    expect(
      reducers(
        initialState,
        actions.checkPowerError({
          item: machines[0],
          payload: "Uh oh!",
        })
      )
    ).toEqual(
      factory.machineState({
        errors: "Uh oh!",
        eventErrors: [
          factory.machineEventError({
            error: "Uh oh!",
            event: "checkPower",
            id: "abc123",
          }),
        ],
        items: machines,
        statuses: { abc123: factory.machineStatus({ checkingPower: false }) },
      })
    );
  });

  it("reduces setSelected", () => {
    const initialState = factory.machineState({
      selected: [] as SelectedMachines,
    });

    expect(
      reducers(initialState, actions.setSelected({ items: ["abcde", "fghij"] }))
    ).toEqual(
      factory.machineState({
        selected: { items: ["abcde", "fghij"] },
      })
    );
  });

  describe("setPool", () => {
    it("reduces setPoolStart", () => {
      const machines = [
        factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
      ];
      const initialState = factory.machineState({
        items: machines,
        statuses: { abc123: factory.machineStatus({ settingPool: false }) },
      });

      expect(
        reducers(
          initialState,
          actions.setPoolStart({
            item: machines[0],
          })
        )
      ).toEqual(
        factory.machineState({
          items: machines,
          statuses: {
            abc123: factory.machineStatus({
              settingPool: true,
            }),
          },
        })
      );
    });

    it("reduces setPoolSuccess", () => {
      const machines = [
        factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
      ];
      const initialState = factory.machineState({
        items: machines,
        statuses: { abc123: factory.machineStatus({ settingPool: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.setPoolSuccess({
            item: machines[0],
          })
        )
      ).toEqual(
        factory.machineState({
          items: machines,
          statuses: {
            abc123: factory.machineStatus({
              settingPool: false,
            }),
          },
        })
      );
    });

    it("reduces setPoolError", () => {
      const machines = [
        factory.machine({ id: 1, system_id: "abc123", hostname: "node1" }),
      ];
      const initialState = factory.machineState({
        errors: null,
        items: machines,
        statuses: { abc123: factory.machineStatus({ settingPool: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.setPoolError({
            item: machines[0],
            payload: "Uh oh",
          })
        )
      ).toEqual(
        factory.machineState({
          errors: "Uh oh",
          eventErrors: [
            factory.machineEventError({
              error: "Uh oh",
              event: "setPool",
              id: "abc123",
            }),
          ],
          items: machines,
          statuses: {
            abc123: factory.machineStatus({
              settingPool: false,
            }),
          },
        })
      );
    });
  });

  it("reduces updateStart", () => {
    const initialState = factory.machineState({ saved: true, saving: false });

    expect(reducers(initialState, actions.updateStart())).toEqual(
      factory.machineState({
        saved: false,
        saving: true,
      })
    );
  });

  describe("clone", () => {
    it("reduces cloneStart", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ cloning: false }) },
      });

      expect(
        reducers(
          initialState,
          actions.cloneStart({
            item: machine,
          })
        )
      ).toEqual(
        factory.machineState({
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              cloning: true,
            }),
          },
        })
      );
    });

    it("reduces cloneSuccess", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ cloning: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.cloneSuccess({
            item: machine,
          })
        )
      ).toEqual(
        factory.machineState({
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              cloning: false,
            }),
          },
        })
      );
    });

    it("reduces cloneError", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ cloning: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.cloneError({
            item: machine,
            payload: "Cloning failed.",
          })
        )
      ).toEqual(
        factory.machineState({
          errors: "Cloning failed.",
          eventErrors: [
            factory.machineEventError({
              error: "Cloning failed.",
              event: NodeActions.CLONE,
              id: "abc123",
            }),
          ],
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              cloning: false,
            }),
          },
        })
      );
    });
  });

  describe("untag", () => {
    it("reduces untagStart", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ untagging: false }) },
      });

      expect(
        reducers(
          initialState,
          actions.untagStart({
            item: machine,
          })
        )
      ).toEqual(
        factory.machineState({
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              untagging: true,
            }),
          },
        })
      );
    });

    it("reduces untagSuccess", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ untagging: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.untagSuccess({
            item: machine,
          })
        )
      ).toEqual(
        factory.machineState({
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              untagging: false,
            }),
          },
        })
      );
    });

    it("reduces untagError", () => {
      const machine = factory.machine({ system_id: "abc123" });
      const initialState = factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus({ untagging: true }) },
      });

      expect(
        reducers(
          initialState,
          actions.untagError({
            item: machine,
            payload: "Untagging failed.",
          })
        )
      ).toEqual(
        factory.machineState({
          errors: "Untagging failed.",
          eventErrors: [
            factory.machineEventError({
              error: "Untagging failed.",
              event: NodeActions.UNTAG,
              id: "abc123",
            }),
          ],
          items: [machine],
          statuses: {
            abc123: factory.machineStatus({
              untagging: false,
            }),
          },
        })
      );
    });
  });

  it("reduces unsubscribeStart", () => {
    const items = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    expect(
      reducers(
        factory.machineState({
          items,
          statuses: {
            abc123: factory.machineStatus(),
            def456: factory.machineStatus(),
          },
        }),
        actions.unsubscribeStart(["abc123"])
      )
    ).toEqual(
      factory.machineState({
        items,
        statuses: {
          abc123: factory.machineStatus({ unsubscribing: true }),
          def456: factory.machineStatus(),
        },
      })
    );
  });

  it("reduces unsubscribeStart for removed statuses", () => {
    const items = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
    expect(
      reducers(
        factory.machineState({
          items,
          statuses: {
            def456: factory.machineStatus(),
          },
        }),
        actions.unsubscribeStart(["abc123"])
      )
    ).toEqual(
      factory.machineState({
        items,
        statuses: {
          def456: factory.machineStatus(),
        },
      })
    );
  });

  it("reduces unsubscribeSuccess", () => {
    const initialState = factory.machineState({
      items: [
        factory.machine({ system_id: "abc123" }),
        factory.machine({ system_id: "def456" }),
      ],
      selected: { items: ["abc123"] },
      statuses: {
        abc123: factory.machineStatus(),
        def456: factory.machineStatus(),
      },
    });
    expect(
      reducers(initialState, actions.unsubscribeSuccess(["abc123"]))
    ).toEqual(
      factory.machineState({
        ...initialState,
        statuses: { ...initialState.statuses, abc123: { ...DEFAULT_STATUSES } },
      })
    );
  });

  it("reduces removeRequest for a details request", () => {
    const initialState = factory.machineState({
      details: {
        [callId]: factory.machineStateDetailsItem(),
      },
    });
    expect(reducers(initialState, actions.removeRequest(callId))).toEqual(
      factory.machineState({
        details: {},
      })
    );
  });

  it("reduces softOff", () => {
    const machine = factory.machine({ system_id: "abc123" });
    const initialState = factory.machineState({
      items: [machine],
      statuses: { abc123: factory.machineStatus() },
    });
    expect(
      reducers(initialState, actions.softOff({ system_id: machine.system_id }))
    ).toEqual(
      factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus() },
      })
    );
  });

  it("reduces softOffStart", () => {
    const machine = factory.machine({ system_id: "abc123" });
    const initialState = factory.machineState({
      items: [machine],
      statuses: { abc123: factory.machineStatus() },
    });
    expect(
      reducers(
        initialState,
        actions.softOffStart({ system_id: machine.system_id })
      )
    ).toEqual(
      factory.machineState({
        items: [machine],
        statuses: { abc123: factory.machineStatus() },
      })
    );
  });
});
