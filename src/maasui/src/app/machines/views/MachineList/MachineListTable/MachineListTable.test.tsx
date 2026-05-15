import { waitFor } from "@testing-library/react";

import { MachineListTable, Label } from "./MachineListTable";

import { SortDirection } from "@/app/base/types";
import { MachineColumns, columnLabels } from "@/app/machines/constants";
import type { Machine, MachineStateListGroup } from "@/app/store/machine/types";
import { FetchGroupKey } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import {
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import { mockUsers, usersResolvers } from "@/testing/resolvers/users";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(
  usersResolvers.listUsers.handler(),
  poolsResolvers.listPools.handler(),
  zoneResolvers.listZones.handler()
);

const callId = "mocked-nanoid";

describe("MachineListTable", () => {
  let state: RootState;
  let machines: Machine[] = [];
  let groups: MachineStateListGroup[] = [];
  beforeEach(() => {
    machines = [
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
        owner: mockUsers.items[0].username,
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
        status: NodeStatus.RELEASING,
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
    groups = [
      factory.machineStateListGroup({
        items: [machines[0].system_id, machines[2].system_id],
        name: "Deployed",
      }),
      factory.machineStateListGroup({
        items: [machines[1].system_id],
        name: "Releasing",
      }),
    ];
    state = factory.rootState({
      general: factory.generalState({
        machineActions: factory.machineActionsState({
          data: [],
        }),
        osInfo: factory.osInfoState({
          data: factory.osInfo({
            osystems: [["ubuntu", "Ubuntu"]],
            releases: [["ubuntu/bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"']],
          }),
          loaded: true,
        }),
      }),
      machine: factory.machineState({
        items: machines,
        lists: {
          [callId]: factory.machineStateList({
            loading: true,
            groups,
          }),
        },
      }),
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("displays skeleton rows when loading", () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={FetchGroupKey.Status}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        machinesLoading
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(
      within(
        screen.getAllByRole("gridcell", {
          name: columnLabels[MachineColumns.FQDN],
        })[0]
      ).getByText("xxxxxxxxx.xxxx")
    ).toBeInTheDocument();
    expect(
      screen.getByRole("grid", {
        name: Label.Loading,
      })
    ).toHaveClass("machine-list--loading");
  });

  it("displays a message if there are no search results", () => {
    groups = [];
    state.machine = factory.machineState({
      items: [],
      lists: {
        [callId]: factory.machineStateList({
          loading: false,
          groups,
        }),
      },
    });

    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter="this does not match anything"
        grouping={FetchGroupKey.Status}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(screen.getByText(Label.NoResults)).toBeInTheDocument();
  });

  it("displays a message if there are no machines", () => {
    groups = [];
    state.machine = factory.machineState({
      items: [],
      lists: {
        [callId]: factory.machineStateList({
          loading: false,
          groups,
        }),
      },
    });

    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={FetchGroupKey.Status}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(screen.getByText(Label.EmptyList)).toBeInTheDocument();
  });

  it("includes groups", () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={FetchGroupKey.Status}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );

    expect(
      screen.queryAllByRole("row", { name: /machines group/i }).length
    ).toEqual(2);
    expect(
      screen.getByRole("row", { name: /Deployed machines group/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("row", { name: /Releasing machines group/i })
    ).toBeInTheDocument();
  });

  it("does not display a group header if the table is ungrouped", () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(
      screen.queryByRole("row", { name: /machines group/i })
    ).not.toBeInTheDocument();
  });

  it("can change machines to display PXE MAC instead of FQDN", async () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );

    const firstMachine = machines[0];
    expect(
      screen.getByRole("checkbox", { name: /koala*/i })
    ).toBeInTheDocument();
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    // Click the MAC table header
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: "MAC" })
    );
    const tableBody = screen.getAllByRole("rowgroup")[1];
    expect(within(tableBody).getAllByRole("link")[0]).toHaveTextContent(
      firstMachine.pxe_mac!
    );
  });

  it("can change machines to display full owners name instead of username", async () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    const tableBody = screen.getAllByRole("rowgroup")[1];
    const getFirstRow = () => within(tableBody).getAllByRole("row")[0];
    const getFirstMachineOwner = () =>
      within(
        within(getFirstRow()).getByRole("gridcell", { name: "Owner" })
      ).getByTestId("owner");
    expect(getFirstMachineOwner()).toHaveTextContent(
      mockUsers.items[0].username
    );
    await userEvent.click(
      within(screen.getByRole("columnheader", { name: "Owner" })).getByRole(
        "button",
        { name: /Name/ }
      )
    );
    await waitFor(() => {
      expect(getFirstMachineOwner()).toHaveTextContent(
        mockUsers.items[0].last_name!
      );
    });
  });

  it("updates sort on header click", async () => {
    const setSortDirection = vi.fn();
    const setSortKey = vi.fn();
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: /cores/i })
    );
    expect(setSortKey).toHaveBeenCalledWith(FetchGroupKey.CpuCount);
    expect(setSortDirection).toHaveBeenCalledWith(SortDirection.DESCENDING);
  });

  it("clears the sort when the same header is clicked and is ascending", async () => {
    const setSortDirection = vi.fn();
    const setSortKey = vi.fn();
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection={SortDirection.ASCENDING}
        sortKey={FetchGroupKey.CpuCount}
        totalPages={1}
      />,
      { state }
    );
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: /cores/i })
    );
    expect(setSortKey).toHaveBeenCalledWith(null);
    expect(setSortDirection).toHaveBeenCalledWith(SortDirection.NONE);
  });

  it("updates the sort when the same header is clicked and is descending", async () => {
    const setSortDirection = vi.fn();
    const setSortKey = vi.fn();
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection={SortDirection.DESCENDING}
        sortKey={FetchGroupKey.CpuCount}
        totalPages={1}
      />,
      { state }
    );
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: /cores/i })
    );
    expect(setSortKey).not.toHaveBeenCalled();
    expect(setSortDirection).toHaveBeenCalledWith(SortDirection.ASCENDING);
  });

  it("updates the sort when the same header is clicked and direction is not set", async () => {
    const setSortDirection = vi.fn();
    const setSortKey = vi.fn();
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection={SortDirection.NONE}
        sortKey={FetchGroupKey.CpuCount}
        totalPages={1}
      />,
      { state }
    );
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: /cores/i })
    );
    expect(setSortKey).not.toHaveBeenCalled();
    expect(setSortDirection).toHaveBeenCalledWith(SortDirection.ASCENDING);
  });

  it("updates the sort when a different header is clicked", async () => {
    const setSortDirection = vi.fn();
    const setSortKey = vi.fn();
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={null}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={setSortDirection}
        setSortKey={setSortKey}
        sortDirection={SortDirection.DESCENDING}
        sortKey={FetchGroupKey.CpuCount}
        totalPages={1}
      />,
      { state }
    );
    const tableHeader = screen.getAllByRole("rowgroup")[0];
    await userEvent.click(
      within(tableHeader).getByRole("button", { name: /power/i })
    );
    expect(setSortKey).toHaveBeenCalledWith(FetchGroupKey.PowerState);
    expect(setSortDirection).toHaveBeenCalledWith(SortDirection.DESCENDING);
  });

  it("displays correct selected string in group header", () => {
    machines[1].status_code = NodeStatusCode.DEPLOYED;
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        filter=""
        grouping={FetchGroupKey.Status}
        groups={groups}
        hiddenGroups={[]}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setHiddenGroups={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(
      within(
        screen.getAllByRole("row", { name: /machines group/i })[0]
      ).getByText("15 machines")
    ).toBeInTheDocument();
  });

  it("shows the correct number of checkboxes", () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        groups={groups}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        showActions={true}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />,
      { state }
    );
    expect(screen.getAllByRole("checkbox").length).toBe(4);
  });

  it("does not show checkboxes if showActions is false", () => {
    renderWithProviders(
      <MachineListTable
        callId={callId}
        currentPage={1}
        groups={groups}
        machineCount={10}
        machines={machines}
        pageSize={20}
        setCurrentPage={vi.fn()}
        setSortDirection={vi.fn()}
        setSortKey={vi.fn()}
        showActions={false}
        sortDirection="none"
        sortKey={null}
        totalPages={1}
      />
    );
    expect(screen.queryAllByRole("checkbox").length).toBe(0);
  });

  describe("hiddenColumns", () => {
    it("can render columns", () => {
      renderWithProviders(
        <MachineListTable
          callId={callId}
          currentPage={1}
          groups={groups}
          hiddenColumns={[]}
          machineCount={10}
          machines={machines}
          pageSize={20}
          setCurrentPage={vi.fn()}
          setSortDirection={vi.fn()}
          setSortKey={vi.fn()}
          sortDirection="none"
          sortKey={null}
          totalPages={1}
        />,
        { state }
      );
      expect(
        screen.getByRole("columnheader", { name: /power/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("columnheader", { name: /zone/i })
      ).toBeInTheDocument();
    });

    it("can hide columns", () => {
      renderWithProviders(
        <MachineListTable
          callId={callId}
          currentPage={1}
          groups={groups}
          hiddenColumns={["power", "zone"]}
          machineCount={10}
          machines={machines}
          pageSize={20}
          setCurrentPage={vi.fn()}
          setSortDirection={vi.fn()}
          setSortKey={vi.fn()}
          sortDirection="none"
          sortKey={null}
          totalPages={1}
        />,
        { state }
      );

      expect(
        screen.queryByRole("columnheader", { name: /power/i })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("columnheader", { name: /zone/i })
      ).not.toBeInTheDocument();
    });

    it("still displays fqdn if showActions is true", () => {
      renderWithProviders(
        <MachineListTable
          callId={callId}
          currentPage={1}
          groups={groups}
          hiddenColumns={["fqdn"]}
          machineCount={10}
          machines={machines}
          pageSize={20}
          setCurrentPage={vi.fn()}
          setSortDirection={vi.fn()}
          setSortKey={vi.fn()}
          showActions
          sortDirection="none"
          sortKey={null}
          totalPages={1}
        />,
        { state }
      );

      expect(
        screen.getByRole("columnheader", { name: /FQDN/i })
      ).toBeInTheDocument();
    });

    it("hides fqdn if if showActions is false", () => {
      renderWithProviders(
        <MachineListTable
          callId={callId}
          currentPage={1}
          groups={groups}
          hiddenColumns={["fqdn"]}
          machineCount={10}
          machines={machines}
          pageSize={20}
          setCurrentPage={vi.fn()}
          setSortDirection={vi.fn()}
          setSortKey={vi.fn()}
          showActions={false}
          sortDirection="none"
          sortKey={null}
          totalPages={1}
        />,
        { state }
      );
      expect(
        screen.queryByRole("columnheader", { name: /FQDN/i })
      ).not.toBeInTheDocument();
    });
  });
});
