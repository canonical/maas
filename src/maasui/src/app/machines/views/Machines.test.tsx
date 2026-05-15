import * as reduxToolkit from "@reduxjs/toolkit";

import { Label } from "./MachineList/MachineListTable/GroupColumn";
import { DEFAULTS } from "./MachineList/MachineListTable/constants";
import Machines from "./Machines";

import { machineActions } from "@/app/store/machine";
import { FetchGroupKey, FilterGroupKey } from "@/app/store/machine/types";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import {
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
  FetchNodeStatus,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { usersResolvers } from "@/testing/resolvers/users";
import {
  renderWithProviders,
  userEvent,
  within,
  screen,
  waitFor,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  usersResolvers.listUsers.handler()
);
vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("Machines", () => {
  let state: RootState;
  const machines = [
    factory.machine({
      actions: [],
      architecture: "amd64/generic",
      cpu_count: 4,
      cpu_test_status: factory.testStatus({
        status: TestStatusStatus.RUNNING,
      }),
      distro_series: "bionic",
      domain: factory.modelRef({
        name: "example",
      }),
      extra_macs: [],
      fqdn: "koala.example",
      hostname: "koala",
      ip_addresses: [],
      memory: 8,
      memory_test_status: factory.testStatus({
        status: TestStatusStatus.PASSED,
      }),
      network_test_status: factory.testStatus({
        status: TestStatusStatus.PASSED,
      }),
      osystem: "ubuntu",
      owner: "admin",
      physical_disk_count: 1,
      pool: factory.modelRef(),
      pxe_mac: "00:11:22:33:44:55",
      spaces: [],
      status: NodeStatus.DEPLOYED,
      status_code: NodeStatusCode.DEPLOYED,
      status_message: "",
      storage: 8,
      storage_test_status: factory.testStatus({
        status: TestStatusStatus.PASSED,
      }),
      testing_status: TestStatusStatus.PASSED,
      system_id: "abc123",
      workload_annotations: { animal: "springbok" },
      zone: factory.modelRef(),
    }),
    factory.machine({
      actions: [],
      architecture: "amd64/generic",
      cpu_count: 2,
      cpu_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      distro_series: "xenial",
      domain: factory.modelRef({
        name: "example",
      }),
      extra_macs: [],
      fqdn: "other.example",
      hostname: "other",
      ip_addresses: [],
      memory: 6,
      memory_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      network_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      osystem: "ubuntu",
      owner: "user",
      physical_disk_count: 2,
      pool: factory.modelRef(),
      pxe_mac: "66:77:88:99:00:11",
      spaces: [],
      status: NodeStatus.RELEASING,
      status_code: NodeStatusCode.RELEASING,
      status_message: "",
      storage: 16,
      storage_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      testing_status: TestStatusStatus.FAILED,
      system_id: "def456",
      zone: factory.modelRef(),
    }),
    factory.machine({
      actions: [],
      architecture: "amd64/generic",
      cpu_count: 2,
      cpu_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      distro_series: "xenial",
      domain: factory.modelRef({
        name: "example",
      }),
      extra_macs: [],
      fqdn: "other.example",
      hostname: "other",
      ip_addresses: [],
      memory: 6,
      memory_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      network_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      osystem: "ubuntu",
      owner: "user",
      physical_disk_count: 2,
      pool: factory.modelRef(),
      pxe_mac: "66:77:88:99:00:11",
      spaces: [],
      status: NodeStatus.FAILED_TESTING,
      status_code: NodeStatusCode.DEPLOYED,
      status_message: "",
      storage: 16,
      storage_test_status: factory.testStatus({
        status: TestStatusStatus.FAILED,
      }),
      testing_status: TestStatusStatus.FAILED,
      system_id: "ghi789",
      zone: factory.modelRef(),
    }),
  ];
  const machineList = factory.machineStateList({
    loaded: true,
    groups: [
      factory.machineStateListGroup({
        items: [machines[0].system_id],
        name: "Deployed",
        value: FetchNodeStatus.DEPLOYED,
      }),
      factory.machineStateListGroup({
        items: [machines[1].system_id],
        name: "Releasing",
        value: FetchNodeStatus.RELEASING,
      }),
      factory.machineStateListGroup({
        items: [machines[2].system_id],
        name: "Failed testing",
        value: FetchNodeStatus.FAILED_TESTING,
      }),
    ],
  });

  beforeEach(() => {
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("123456");
    state = factory.rootState({
      general: factory.generalState({
        machineActions: {
          data: [],
          errors: null,
          loaded: false,
          loading: false,
        },
        vaultEnabled: factory.vaultEnabledState({ data: false, loaded: true }),
        osInfo: {
          data: factory.osInfo({
            osystems: [["ubuntu", "Ubuntu"]],
            releases: [["ubuntu/bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"']],
          }),
          errors: null,
          loaded: true,
          loading: false,
        },
        version: {
          data: "2.8.0",
          errors: null,
          loaded: true,
          loading: false,
        },
      }),
      controller: factory.controllerState({
        loaded: true,
        items: [factory.controller({ vault_configured: false })],
      }),
      machine: factory.machineState({
        items: machines,
        lists: {
          "78910": machineList,
        },
        filters: [
          factory.machineFilterGroup({
            key: FilterGroupKey.Workloads,
            loaded: true,
            options: [{ key: "animal:springbok", label: "animal: springbok" }],
          }),
        ],
        filtersLoaded: true,
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
      }),
      router: factory.routerState(),
    });
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("can set the search from the URL", async () => {
    renderWithProviders(<Machines />, {
      initialEntries: ["/machines?q=test+search"],
      state,
    });
    await waitFor(() => {
      expect(screen.getByRole("searchbox", { name: "Search" })).toHaveValue(
        "test search"
      );
    });
  });

  it("changes the URL when the search text changes", async () => {
    const { router } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines?q=test+search"],
      state,
    });
    await userEvent.clear(screen.getByRole("searchbox", { name: "Search" }));
    await userEvent.type(
      screen.getByRole("searchbox", { name: "Search" }),
      "status:new"
    );
    await waitFor(() => {
      expect(router.state.location.search).toBe("?status=new");
    });
  });

  it("can hide groups", async () => {
    vi.spyOn(query, "generateCallId")
      .mockReturnValueOnce("123456")
      .mockReturnValueOnce("78910");

    const { store } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });
    const expected = machineActions.fetch("123456", {
      group_collapsed: ["failed_testing"],
    });
    const getFetchActions = () =>
      store.getActions().filter((action) => action.type === expected.type);
    const initialFetchActions = getFetchActions();
    await waitFor(() => {
      expect(initialFetchActions).toHaveLength(1);
    });
    // Click the button to toggle the group.
    await userEvent.click(
      within(
        screen.getByRole("row", { name: "Failed testing machines group" })
      ).getByRole("button", { name: Label.HideGroup })
    );
    await waitFor(() => {
      expect(getFetchActions()).toHaveLength(2);
    });
    const finalFetchAction = getFetchActions()[1];
    expect(finalFetchAction.payload.params.group_collapsed).toStrictEqual([
      "failed_testing",
    ]);
  });

  it("can change groups", async () => {
    vi.spyOn(reduxToolkit, "nanoid")
      .mockReturnValueOnce("mocked-nanoid-1")
      .mockReturnValueOnce("mocked-nanoid-2");
    // Create two pages of machines.
    state.machine.items = Array.from(Array(DEFAULTS.pageSize * 2)).map(() =>
      factory.machine()
    );
    state.machine.lists = {
      "mocked-nanoid-2": factory.machineStateList({
        count: state.machine.items.length,
        groups: [
          factory.machineStateListGroup({
            // Insert the ids of all machines in the list's group.
            items: state.machine.items.map(({ system_id }) => system_id),
          }),
        ],
      }),
    };

    const expected = machineActions.fetch("123456", {
      group_key: FetchGroupKey.Owner,
    });
    const { store } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });
    const getFetchActions = () =>
      store.getActions().filter((action) => action.type === expected.type);

    const initialFetchActions = getFetchActions();
    await waitFor(() => {
      expect(initialFetchActions).toHaveLength(1);
    });

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /Group by/i }),
      screen.getByRole("option", { name: "Group by owner" })
    );
    await waitFor(() => {
      expect(getFetchActions()).toHaveLength(2);
    });
    const finalFetchAction = getFetchActions()[1];
    expect(finalFetchAction.payload.params.group_key).toBe(FetchGroupKey.Owner);
  });

  it("can store the group in local storage", async () => {
    const {
      result: { unmount },
    } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /Group by/i }),
      screen.getByRole("option", { name: "Group by owner" })
    );
    unmount();
    // Render another machine list, this time it should restore the value
    // set by the select.
    renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });

    expect(localStorage.getItem("grouping")).toBe('"owner"');
  });

  it("uses the default fallback value for invalid stored grouping values", async () => {
    localStorage.setItem("grouping", '"invalid_value"');
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");

    const { store } = renderWithProviders(<Machines />, { state });
    expect(screen.getByRole("combobox", { name: /Group by/ })).toHaveValue(
      DEFAULTS.grouping
    );
    const expected = machineActions.fetch("123456", {
      group_key: DEFAULTS.grouping,
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches).toHaveLength(1);
    expect(fetches.at(-1).payload.params.group_key).toBe(DEFAULTS.grouping);
  });

  it("can store hidden groups in local storage", async () => {
    vi.spyOn(query, "generateCallId")
      .mockReturnValueOnce("mocked-nanoid-1")
      .mockReturnValueOnce("mocked-nanoid-2");
    state.machine.lists = {
      "mocked-nanoid-1": machineList,
      "mocked-nanoid-2": machineList,
    };

    const {
      result: { unmount },
      store,
    } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });
    const expected = machineActions.fetch("123456", {
      group_collapsed: [],
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(
      fetches[fetches.length - 1].payload.params.group_collapsed
    ).toStrictEqual([]);
    // Click the button to toggle the group.
    await userEvent.click(
      within(
        screen.getByRole("row", { name: "Deployed machines group" })
      ).getByRole("button", { name: Label.HideGroup })
    );
    // Render another machine list, this time it should restore the
    // hidden group state.
    unmount();
    const { store: store2 } = renderWithProviders(<Machines />, {
      initialEntries: ["/machines"],
      state,
    });
    const expected2 = machineActions.fetch("123456", {
      group_collapsed: ["deployed"],
    });
    const fetches2 = store2
      .getActions()
      .filter((action) => action.type === expected2.type);
    expect(
      fetches2[fetches.length - 1].payload.params.group_collapsed
    ).toStrictEqual(["deployed"]);
  });

  it("correctly sets the search text for workload annotation filters", async () => {
    renderWithProviders(<Machines />, { initialEntries: ["/machines"], state });

    await userEvent.click(screen.getByRole("button", { name: "Filters" }));
    await userEvent.click(screen.getByRole("tab", { name: "Workload" }));

    await userEvent.click(screen.getByRole("checkbox", { name: "animal (1)" }));

    await waitFor(() => {
      expect(screen.getByRole("searchbox")).toHaveValue("workload-animal:()");
    });

    expect(screen.getByRole("checkbox", { name: "animal (1)" })).toBeChecked();
  });
});
