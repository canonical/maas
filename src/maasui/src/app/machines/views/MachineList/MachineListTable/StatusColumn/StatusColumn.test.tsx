import { StatusColumn } from "./StatusColumn";

import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { PowerState } from "@/app/store/types/enum";
import {
  NodeActions,
  NodeStatus,
  NodeStatusCode,
  TestStatusStatus,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  userEvent,
  screen,
  within,
  expectTooltipOnHover,
} from "@/testing/utils";

describe("StatusColumn", () => {
  let state: RootState;
  let machine: Machine;

  beforeEach(() => {
    machine = factory.machine({
      actions: [],
      distro_series: "bionic",
      osystem: "ubuntu",
      status: NodeStatus.NEW,
      status_code: 0,
      status_message: "",
      system_id: "abc123",
    });
    state = factory.rootState({
      general: factory.generalState({
        osInfo: factory.osInfoState({
          data: factory.osInfo({
            osystems: [
              ["centos", "CentOS"],
              ["ubuntu", "Ubuntu"],
            ],
            releases: [
              ["centos/centos70", "CentOS 7"],
              ["ubuntu/xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"'],
              ["ubuntu/bionic", 'Ubuntu 18.04 LTS "Bionic Beaver"'],
            ],
          }),
          errors: {},
          loaded: true,
          loading: false,
        }),
      }),
      machine: factory.machineState({
        items: [machine],
        errors: {},
        loaded: true,
        loading: false,
      }),
    });
  });

  describe("status text", () => {
    it("displays the machine's status if not deploying or deployed", () => {
      machine.status = NodeStatus.NEW;
      machine.status_code = NodeStatusCode.NEW;

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );

      expect(screen.getByTestId("status-text")).toHaveTextContent("New");
    });

    it("displays the short-form of Ubuntu release if deployed", () => {
      machine.status = NodeStatus.DEPLOYED;
      machine.status_code = NodeStatusCode.DEPLOYED;
      machine.osystem = "ubuntu";
      machine.distro_series = "bionic";

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );

      expect(screen.getByTestId("status-text")).toHaveTextContent(
        "Ubuntu 18.04 LTS"
      );
    });

    it("displays the full OS and release if non-Ubuntu deployed", () => {
      machine.status = NodeStatus.DEPLOYED;
      machine.status_code = NodeStatusCode.DEPLOYED;
      machine.osystem = "centos";
      machine.distro_series = "centos70";

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      expect(screen.getByTestId("status-text")).toHaveTextContent("CentOS 7");
    });

    it("displays 'Deploying OS release' if machine is deploying", () => {
      machine.status = NodeStatus.DEPLOYING;
      machine.status_code = NodeStatusCode.DEPLOYING;
      machine.osystem = "ubuntu";
      machine.distro_series = "bionic";

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      expect(screen.getByTestId("status-text")).toHaveTextContent(
        "Deploying Ubuntu 18.04 LTS"
      );
    });

    it("displays an error message for broken machines", () => {
      machine.error_description = "machine is on fire";
      machine.status = NodeStatus.BROKEN;
      machine.status_code = NodeStatusCode.BROKEN;

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );

      expect(screen.getByTestId("error-text")).toHaveTextContent(
        "machine is on fire"
      );
    });
  });

  describe("progress text", () => {
    it("displays the machine's status_message if in a transient state", () => {
      machine.status = NodeStatus.TESTING;
      machine.status_code = NodeStatusCode.TESTING;
      machine.status_message = "2 of 6 tests complete";

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );

      expect(screen.getByTestId("progress-text")).toHaveTextContent(
        "2 of 6 tests complete"
      );
    });

    it(`does not display the machine's status_message if
      not in a transient state`, () => {
      machine.status = NodeStatus.ALLOCATED;
      machine.status_code = NodeStatusCode.ALLOCATED;
      machine.status_message = "This machine is allocated";

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      expect(screen.getByTestId("progress-text")).toHaveTextContent("");
    });
  });

  describe("status icon", () => {
    it("shows a spinner if machine is in a transient state", () => {
      machine.status = NodeStatus.COMMISSIONING;
      machine.status_code = NodeStatusCode.COMMISSIONING;

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      expect(screen.getByText(/Loading/i)).toBeInTheDocument();
    });

    it(`shows a warning and tooltip if machine has failed tests and is not in a
      state where the warning should be hidden`, () => {
      machine.status = NodeStatus.ALLOCATED;
      machine.status_code = NodeStatusCode.ALLOCATED;
      machine.testing_status = TestStatusStatus.FAILED;

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      expect(screen.getByLabelText(/warning/i)).toBeInTheDocument();
    });

    it("can show a menu with all possible options", async () => {
      machine.actions = [
        NodeActions.ABORT,
        NodeActions.ACQUIRE,
        NodeActions.COMMISSION,
        NodeActions.DEPLOY,
        NodeActions.EXIT_RESCUE_MODE,
        NodeActions.LOCK,
        NodeActions.MARK_BROKEN,
        NodeActions.MARK_FIXED,
        NodeActions.OVERRIDE_FAILED_TESTING,
        NodeActions.RELEASE,
        NodeActions.RESCUE_MODE,
        NodeActions.TEST,
        NodeActions.UNLOCK,
      ];
      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );
      await userEvent.click(
        screen.getByRole("button", { name: /take action/i })
      );
      expect(
        within(screen.getByLabelText("submenu")).getAllByRole("button")
      ).toHaveLength(machine.actions.length);
      machine.actions.forEach((action) => {
        expect(
          within(screen.getByLabelText("submenu")).getByRole("button", {
            name: action,
          })
        ).toBeInTheDocument();
      });
    });

    it("does not render table menu if onToggleMenu not provided", () => {
      renderWithProviders(<StatusColumn systemId="abc123" />, {
        state,
      });
      expect(
        screen.queryByRole("button", { name: /take action/i })
      ).not.toBeInTheDocument();
    });

    it("shows an error icon button and a tooltip if power type is not set and status is unknown", async () => {
      machine.power_state = PowerState.UNKNOWN;
      machine.status_code = NodeStatusCode.NEW;

      renderWithProviders(
        <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
        { state }
      );

      const button = screen.getByRole("button", {
        name: "Unconfigured power type",
      });
      expect(button).toBeInTheDocument();

      await expectTooltipOnHover(
        button,
        "Unconfigured power type. Go to the configuration tab of this machine."
      );
    });
  });

  it('displays a "Deployed in memory" status for epmerally deployed machines', () => {
    machine.ephemeral_deploy = true;
    machine.status_code = NodeStatusCode.DEPLOYED;

    renderWithProviders(
      <StatusColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByText(/deployed in memory/i)).toBeInTheDocument();
  });
});
