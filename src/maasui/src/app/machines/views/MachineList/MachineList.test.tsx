import * as reduxToolkit from "@reduxjs/toolkit";

import MachineList from "./MachineList";
import { DEFAULTS } from "./MachineListTable/constants";

import { machineActions } from "@/app/store/machine";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import {
  FetchNodeStatus,
  NodeStatus,
  NodeStatusCode,
  NodeType,
  TestStatusStatus,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { fireEvent, renderWithProviders, screen } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("MachineList", () => {
  let state: RootState;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
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
      }),
      controller: factory.controllerState({
        loaded: true,
        items: [factory.controller({ vault_configured: false })],
      }),
      machine: factory.machineState({
        items: machines,
        lists: {
          "123456": factory.machineStateList({
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
          }),
        },
        filters: [factory.machineFilterGroup()],
        filtersLoaded: true,
      }),
    });
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("can display an error", () => {
    state.machine.errors = "Uh oh!";
    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText("Uh oh!")).toBeInTheDocument();
  });

  it("can display and close an error from machine list", () => {
    state.machine.errors = null;
    state.machine.lists["123456"].errors = { tag: "No such constraint." };
    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText("tag: No such constraint.")).toBeInTheDocument();

    // Using fireEvent instead of userEvent here,
    // since using the latter seems to break every other test in this file

    // eslint-disable-next-line testing-library/prefer-user-event
    fireEvent.click(screen.getByRole("button", { name: "Close notification" }));
    expect(
      screen.queryByText("tag: No such contraint.")
    ).not.toBeInTheDocument();
  });

  it("can display a list of errors", () => {
    state.machine.errors = ["Uh oh!", "It broke"];
    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByText("Uh oh! It broke")).toBeInTheDocument();
  });

  it("can display a collection of errors", () => {
    state.machine.errors = { machine: "Uh oh!", network: "It broke" };
    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    expect(
      screen.getByText("machine: Uh oh! network: It broke")
    ).toBeInTheDocument();
  });

  it("dispatches action to clean up machine state when dismissing errors", () => {
    state.machine.errors = "Everything is broken.";
    const { store } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    // Using fireEvent instead of userEvent here,
    // since using the latter seems to break every other test in this file

    // eslint-disable-next-line testing-library/prefer-user-event
    fireEvent.click(screen.getByRole("button", { name: "Close notification" }));

    expect(
      store.getActions().some((action) => action.type === "machine/cleanup")
    ).toBe(true);
  });

  it("displays a message if there are no search results", async () => {
    state.machine.lists = {
      "123456": factory.machineStateList({
        count: 0,
        groups: [],
      }),
    };
    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter="no matches here mate"
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    expect(
      screen.getByText("No machines match the search criteria.")
    ).toBeInTheDocument();
  });

  it("cleans up when unmounting", async () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    unmount();

    expect(
      store.getActions().some((action) => action.type === "machine/cleanup")
    ).toBe(true);
    expect(
      store.getActions().find((action) => action.type === "machine/setSelected")
    ).toStrictEqual({
      type: "machine/setSelected",
      payload: null,
    });
  });

  it("can search", () => {
    const { store } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter="free text workload-service:prod"
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    const filter = {
      free_text: ["free text"],
      workloads: ["service:prod"],
    };
    const expected = machineActions.fetch("123456", {
      filter,
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches[fetches.length - 1].payload.params.filter).toStrictEqual(
      filter
    );
  });

  it("can change pages", async () => {
    vi.spyOn(query, "generateCallId")
      .mockReturnValueOnce("mocked-nanoid-1")
      .mockReturnValueOnce("mocked-nanoid-2");
    // Create two pages of machines.
    state.machine.items = Array.from(Array(DEFAULTS.pageSize * 2)).map(() =>
      factory.machine()
    );
    state.machine.lists = {
      "mocked-nanoid-1": factory.machineStateList({
        count: state.machine.items.length,
        groups: [
          factory.machineStateListGroup({
            // Insert the ids of all machines in the list's group.
            items: state.machine.items.map(({ system_id }) => system_id),
          }),
        ],
      }),
    };
    const { store } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    // Using fireEvent instead of userEvent here,
    // since using the latter seems to break every other test in this file
    // eslint-disable-next-line testing-library/prefer-user-event
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    const expected = machineActions.fetch("123456", {
      page_number: 2,
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches).toHaveLength(2);
    expect(fetches[fetches.length - 1].payload.params.page_number).toBe(2);
  });

  it("shows a warning notification if not all controllers are configured with Vault", async () => {
    state.controller.items = [
      factory.controller({
        system_id: "abc123",
        vault_configured: true,
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        system_id: "def456",
        vault_configured: false,
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
    ];

    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    expect(screen.getByTestId("vault-notification")).toHaveTextContent(
      "Configure 1 other controller with Vault to complete integration with Vault."
    );
  });

  it("shows a warning notification if  all controllers are configured with Vault but secrets are not migrated", async () => {
    state.controller.items = [
      factory.controller({
        system_id: "abc123",
        vault_configured: true,
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        system_id: "def456",
        vault_configured: true,
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
    ];

    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    expect(screen.getByTestId("vault-notification")).toHaveTextContent(
      "Migrate your secrets to Vault to complete integration with Vault."
    );
  });

  it("doesn't show a warning notification if Vault setup has not been started", async () => {
    state.controller.items = [
      factory.controller({
        system_id: "abc123",
        vault_configured: false,
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        system_id: "def456",
        vault_configured: false,
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
    ];

    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    expect(screen.queryByTestId("vault-notification")).not.toBeInTheDocument();
  });

  it("doesn't show a warning notification if Vault is fully configured", async () => {
    state.controller.items = [
      factory.controller({
        system_id: "abc123",
        vault_configured: true,
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        system_id: "def456",
        vault_configured: true,
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
    ];
    state.general = factory.generalState({
      vaultEnabled: factory.vaultEnabledState({
        data: true,
        loaded: true,
      }),
    });

    renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );

    expect(screen.queryByTestId("vault-notification")).not.toBeInTheDocument();
  });

  it("uses the stored machineListPageSize", () => {
    localStorage.setItem("machineListPageSize", "20");
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
    const { store } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    const expected = machineActions.fetch("123456", {
      page_size: 20,
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches).toHaveLength(1);
    expect(fetches.at(-1).payload.params.page_size).toBe(20);
  });

  it("falls back to default for invalid stored machineListPageSize", () => {
    localStorage.setItem("machineListPageSize", '"invalid_value"');
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
    const { store } = renderWithProviders(
      <MachineList
        grouping={null}
        hiddenColumns={[]}
        hiddenGroups={[]}
        searchFilter=""
        setHiddenGroups={vi.fn()}
      />,
      { state }
    );
    const expected = machineActions.fetch("123456", {
      page_size: DEFAULTS.pageSize,
    });
    const fetches = store
      .getActions()
      .filter((action) => action.type === expected.type);
    expect(fetches).toHaveLength(1);
    expect(fetches.at(-1).payload.params.page_size).toBe(DEFAULTS.pageSize);
  });
});
