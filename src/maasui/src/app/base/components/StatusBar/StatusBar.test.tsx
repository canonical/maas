import StatusBar from "./StatusBar";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus, NodeType } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;
const originalEnv = import.meta.env;

beforeEach(() => {
  vi.useFakeTimers();
  // Thu, 31 Dec. 2020 23:00:00 UTC
  vi.setSystemTime(new Date(Date.UTC(2020, 11, 31, 23, 0, 0)));
  state = factory.rootState({
    config: factory.configState({
      items: [factory.config({ name: ConfigNames.MAAS_NAME, value: "bolla" })],
    }),
    controller: factory.controllerState({
      items: [],
    }),
    general: factory.generalState({
      version: factory.versionState({ data: "2.10.0" }),
    }),
    machine: factory.machineState({
      active: "abc123",
      items: [],
    }),
  });
});

afterEach(() => {
  vi.useRealTimers();
  Object.assign(import.meta.env, { ...originalEnv });
});

it("can show if the MAAS is a snap installation", () => {
  state.general.installType.data = "snap";

  renderWithProviders(<StatusBar />, { state });

  expect(screen.getByText(/(snap)/i)).toBeInTheDocument();
});

it("can show if the MAAS is a deb installation", () => {
  state.general.installType.data = "deb";

  renderWithProviders(<StatusBar />, { state });

  expect(screen.getByText(/(deb)/i)).toBeInTheDocument();
});

it("can show if a machine is currently commissioning", () => {
  state.machine.items = [
    factory.machineDetails({
      fqdn: "test.maas",
      status: NodeStatus.COMMISSIONING,
      system_id: "abc123",
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(screen.getByText(/Commissioning in progress.../)).toBeInTheDocument();
});

it("can show if a machine has not been commissioned yet", () => {
  state.machine.items = [
    factory.machineDetails({
      commissioning_start_time: factory.timestamp(""),
      fqdn: "test.maas",
      system_id: "abc123",
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(screen.getByText(/Not yet commissioned/)).toBeInTheDocument();
});

it("can show the last time a machine was commissioned", () => {
  state.machine.items = [
    factory.machineDetails({
      enable_hw_sync: false,
      commissioning_start_time: factory.timestamp("Thu, 31 Dec. 2020 22:59:00"),
      fqdn: "test.maas",
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.getByText(/Last commissioned: 1 minute ago/)
  ).toBeInTheDocument();
});

it("can handle an incorrectly formatted commissioning timestamp", () => {
  state.machine.items = [
    factory.machineDetails({
      enable_hw_sync: false,
      commissioning_start_time: factory.timestamp("2020-03-01 09:12:43"),
      fqdn: "test.maas",
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.getByText(/Unable to parse commissioning timestamp/)
  ).toBeInTheDocument();
});

it("displays Last and Next sync instead of Last commissioned date for deployed machines with hardware sync enabled ", () => {
  state.machine.items = [
    factory.machineDetails({
      commissioning_start_time: factory.timestamp("Thu, 31 Dec. 2020 22:59:00"),
      fqdn: "test.maas",
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
      enable_hw_sync: true,
      last_sync: factory.timestamp("Thu, 31 Dec. 2020 22:00:00"),
      next_sync: factory.timestamp("Thu, 31 Dec. 2020 23:01:00"),
    }),
  ];

  renderWithProviders(<StatusBar />, { state: state });

  expect(screen.getByTestId("status-bar-status")).not.toHaveTextContent(
    /Last commissioned/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /test.maas/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /Last synced: about 1 hour ago/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /Next sync: in 1 minute/
  );
});

it("doesn't display last or next sync for deploying machines with hardware sync enabled", () => {
  state.machine.items = [
    factory.machineDetails({
      commissioning_start_time: factory.timestamp("Thu, 31 Dec. 2020 22:59:00"),
      fqdn: "test.maas",
      status: NodeStatus.DEPLOYING,
      system_id: "abc123",
      enable_hw_sync: true,
      last_sync: factory.timestamp("Thu, 31 Dec. 2020 22:00:00"),
      next_sync: factory.timestamp("Thu, 31 Dec. 2020 23:01:00"),
    }),
  ];

  renderWithProviders(<StatusBar />, {
    state,
  });

  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /Last commissioned/
  );
  expect(screen.getByTestId("status-bar-status")).not.toHaveTextContent(
    /Last synced/
  );
  expect(screen.getByTestId("status-bar-status")).not.toHaveTextContent(
    /Next sync/
  );
});

it("displays correct text for machines with hardware sync enabled and no last_sync or next_sync", () => {
  state.machine.items = [
    factory.machineDetails({
      commissioning_start_time: factory.timestamp("Thu, 31 Dec. 2020 22:59:00"),
      fqdn: "test.maas",
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
      enable_hw_sync: true,
      last_sync: factory.timestamp(""),
      next_sync: factory.timestamp(""),
    }),
  ];

  renderWithProviders(<StatusBar />, {
    state,
  });

  expect(screen.getByTestId("status-bar-status")).not.toHaveTextContent(
    /Last commissioned/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /test.maas/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /Last synced: Never/
  );
  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    /Next sync: Never/
  );
});

it("displays last image sync timestamp for a rack or region+rack controller", () => {
  const controller = factory.controllerDetails({
    last_image_sync: factory.timestamp("Thu, 02 Jun. 2022 00:48:41"),
    node_type: NodeType.RACK_CONTROLLER,
  });
  state.controller.active = controller.system_id;
  state.controller.items = [controller];

  renderWithProviders(<StatusBar />, { state });

  expect(screen.getByTestId("status-bar-status")).toHaveTextContent(
    `Last image sync: Thu, 02 Jun. 2022 00:48:41 (UTC)`
  );
});

it("displays the feedback link when analytics enabled and not in development environment", () => {
  Object.assign(import.meta.env, { ...originalEnv, DEV: false });

  state.config = factory.configState({
    items: [
      ...state.config.items,
      factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: true }),
    ],
  });

  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.getByRole("button", { name: "Give feedback" })
  ).toBeInTheDocument();
});

it("hides the feedback link when analytics disabled", () => {
  Object.assign(import.meta.env, { ...originalEnv, DEV: false });
  state.config = factory.configState({
    items: [
      ...state.config.items,
      factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: false }),
    ],
  });
  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.queryByRole("button", { name: "Give feedback" })
  ).not.toBeInTheDocument();
});

it("hides the feedback link in development environment", () => {
  Object.assign(import.meta.env, { ...originalEnv, DEV: true });
  state.config = factory.configState({
    items: [
      ...state.config.items,
      factory.config({ name: ConfigNames.ENABLE_ANALYTICS, value: true }),
    ],
  });
  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.queryByRole("button", { name: "Give feedback" })
  ).not.toBeInTheDocument();
});

it("displays the status message when connected to MAAS Site Manager", () => {
  state.msm = factory.msmState({
    status: factory.msmStatus({
      running: "not_connected",
    }),
  });

  const { rerender } = renderWithProviders(<StatusBar />, { state });

  expect(
    screen.queryByText("Connected to MAAS Site Manager")
  ).not.toBeInTheDocument();

  state.msm = factory.msmState({
    status: factory.msmStatus({
      running: "connected",
    }),
  });

  rerender(<StatusBar />, { state });

  expect(
    screen.getByText("Connected to MAAS Site Manager")
  ).toBeInTheDocument();
});

it("correctly calculates the last commissioned time when multiple commissioning events are present", () => {
  state.machine.items = [
    factory.machineDetails({
      fqdn: "multi-event.maas",
      enable_hw_sync: false,
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
      events: [
        factory.machineEvent({
          type: factory.machineEventType({
            description: NodeStatus.COMMISSIONING,
          }),
          created: factory.timestamp("Thu, 31 Dec. 2020 21:00:00"),
        }),
        factory.machineEvent({
          type: factory.machineEventType({
            description: NodeStatus.COMMISSIONING,
          }),
          created: factory.timestamp("Thu, 31 Dec. 2020 22:00:00"),
        }),
        factory.machineEvent({
          type: factory.machineEventType({
            description: NodeStatus.COMMISSIONING,
          }),
          created: factory.timestamp("Thu, 31 Dec. 2020 20:00:00"),
        }),
      ],
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.getByText(/Last commissioned: about 1 hour ago/)
  ).toBeInTheDocument();
});

it("handles invalid commissioning event timestamp", () => {
  state.machine.items = [
    factory.machineDetails({
      fqdn: "invalid-timestamp.maas",
      status: NodeStatus.DEPLOYED,
      system_id: "abc123",
      enable_hw_sync: false,
      events: [
        factory.machineEvent({
          type: factory.machineEventType({
            description: NodeStatus.COMMISSIONING,
          }),
          created: factory.timestamp("invalid-date"),
        }),
      ],
    }),
  ];

  renderWithProviders(<StatusBar />, { state });

  expect(
    screen.getByText(/Unable to parse commissioning timestamp/)
  ).toBeInTheDocument();
});
