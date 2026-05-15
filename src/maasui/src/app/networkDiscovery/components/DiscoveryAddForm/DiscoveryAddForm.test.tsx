import DiscoveryAddForm, {
  Labels as DiscoveryAddFormLabels,
} from "./DiscoveryAddForm";
import { Labels as FormFieldLabels } from "./DiscoveryAddFormFields/DiscoveryAddFormFields";
import { DeviceType } from "./types";

import { deviceActions } from "@/app/store/device";
import { DeviceIpAssignment, DeviceMeta } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import {
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
} from "@/app/store/types/node";
import { callId, enableCallIdMocks } from "@/testing/callId-mock";
import * as factory from "@/testing/factories";
import { mockFormikFormSaved } from "@/testing/mockFormikFormSaved";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

enableCallIdMocks();

describe("DiscoveryAddForm", () => {
  let state: RootState;
  const discovery = factory.discovery({
    ip: "1.2.3.4",
    mac_address: "aa:bb:cc",
    subnet_id: 9,
    vlan_id: 8,
    hostname: "discovery-hostname.domain-name",
  });

  beforeEach(() => {
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
        permissions: ["edit", "delete"],
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
    ];
    state = factory.rootState({
      device: factory.deviceState({
        loaded: true,
        items: [
          factory.device({ system_id: "abc123", fqdn: "abc123.example" }),
        ],
      }),
      domain: factory.domainState({
        loaded: true,
        items: [factory.domain({ name: "local" })],
      }),
      machine: factory.machineState({
        loaded: true,
        items: machines,
        lists: {
          [callId]: factory.machineStateList({
            loaded: true,
            groups: [
              factory.machineStateListGroup({
                items: [machines[0].system_id],
                name: "Deployed",
              }),
            ],
          }),
        },
      }),
      subnet: factory.subnetState({ loaded: true }),
      vlan: factory.vlanState({ loaded: true }),
    });
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={discovery} />,
      { state }
    );
    const expectedActions = [
      "device/fetch",
      "domain/fetch",
      "machine/fetch",
      "subnet/fetch",
      "vlan/fetch",
    ];
    expectedActions.forEach((expectedAction) => {
      expect(
        store.getActions().some((action) => action.type === expectedAction)
      );
    });
  });

  it("displays a spinner when data is loading", () => {
    state.device.loaded = false;
    state.domain.loaded = false;
    state.machine.loaded = false;
    state.subnet.loaded = false;
    state.vlan.loaded = false;

    renderWithProviders(<DiscoveryAddForm discovery={discovery} />, { state });
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it.skip("maps name errors to hostname", async () => {
    // Render the form with default state.
    const { rerender } = renderWithProviders(
      <DiscoveryAddForm discovery={discovery} />,
      { state }
    );
    const error = "Name is invalid";
    // Change the device state to included the errors (as if it has changed via an API response).
    state.device.errors = { name: error };
    // Rerender the form to simulate the state change.
    rerender(<DiscoveryAddForm discovery={discovery} />, {
      state,
    });
    expect(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.Hostname}`,
      })
      // react-components uses aria-errormessage to link the errors to the inputs so we can use the toHaveAccessibleErrorMessage helper here.
    ).toHaveAccessibleErrorMessage(error);
  });

  it("can dispatch to create a device", async () => {
    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={discovery} />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldLabels.Domain }),
      "local"
    );

    await userEvent.click(
      screen.getByRole("button", {
        name: "Select parent (optional) - open list",
      })
    );
    await userEvent.click(
      within(screen.getByRole("listbox")).getByText("abc123")
    );

    await userEvent.clear(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.Hostname}`,
      })
    );

    await userEvent.type(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.Hostname}`,
      }),
      "koala"
    );

    await userEvent.click(
      screen.getByRole("button", { name: DiscoveryAddFormLabels.SubmitLabel })
    );

    expect(
      store.getActions().find((action) => action.type === "device/create")
    ).toStrictEqual(
      deviceActions.create({
        domain: { name: "local" },
        extra_macs: [],
        hostname: "koala",
        interfaces: [
          {
            ip_address: "1.2.3.4",
            ip_assignment: DeviceIpAssignment.DYNAMIC,
            mac: "aa:bb:cc",
            subnet: 9,
          },
        ],
        parent: "abc123",
        primary_mac: "aa:bb:cc",
      })
    );
  });

  it("can dispatch to create a device interface", async () => {
    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={discovery} />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldLabels.Type }),
      DeviceType.INTERFACE
    );

    await userEvent.clear(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.InterfaceName}`,
      })
    );

    await userEvent.type(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.InterfaceName}`,
      }),
      "koala"
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "IP assignment" }),
      DeviceIpAssignment.DYNAMIC
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldLabels.DeviceName }),
      "abc123"
    );

    await userEvent.click(
      screen.getByRole("button", { name: DiscoveryAddFormLabels.SubmitLabel })
    );

    await waitFor(() => {
      expect(
        store
          .getActions()
          .find((action) => action.type === "device/createInterface")
      ).toStrictEqual(
        deviceActions.createInterface({
          [DeviceMeta.PK]: "abc123",
          ip_address: "1.2.3.4",
          ip_assignment: DeviceIpAssignment.DYNAMIC,
          mac_address: "aa:bb:cc",
          name: "koala",
          subnet: "9",
          vlan: 8,
        })
      );
    });
  });

  it("displays a success message when a hostname is provided", async () => {
    mockFormikFormSaved();

    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={discovery} />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("button", { name: DiscoveryAddFormLabels.SubmitLabel })
    );

    expect(
      store.getActions().find((action) => action.type === "message/add").payload
        .message
    ).toBe("discovery-hostname has been added.");
  });

  it("displays a success message for a device with no hostname", async () => {
    mockFormikFormSaved();

    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={factory.discovery({ hostname: "" })} />,
      { state }
    );

    await userEvent.clear(
      screen.getByRole("textbox", {
        name: `${FormFieldLabels.Hostname}`,
      })
    );

    await userEvent.click(
      screen.getByRole("button", { name: DiscoveryAddFormLabels.SubmitLabel })
    );

    expect(
      store.getActions().find((action) => action.type === "message/add").payload
        .message
    ).toBe("A device has been added.");
  });

  it("displays a success message for an interface with no hostname", async () => {
    const { store } = renderWithProviders(
      <DiscoveryAddForm discovery={factory.discovery({ hostname: "" })} />,
      { state }
    );

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: FormFieldLabels.Type }),
      DeviceType.INTERFACE
    );

    mockFormikFormSaved();
    // rerender(<DiscoveryAddForm discovery={discovery} />);

    await userEvent.click(
      screen.getByRole("button", { name: DiscoveryAddFormLabels.SubmitLabel })
    );

    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === "message/add")
          .payload.message
      ).toBe("An interface has been added.");
    });
  });
});
