import * as reduxToolkit from "@reduxjs/toolkit";

import MachineHeader from "./MachineHeader";

import { machineActions } from "@/app/store/machine";
import type { RootState } from "@/app/store/root/types";
import { PowerState } from "@/app/store/types/enum";
import {
  NodeActions,
  NodeStatus,
  NodeStatusCode,
} from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("MachineHeader", () => {
  let state: RootState;
  beforeEach(() => {
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("123456");
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machineDetails({ fqdn: "test-machine", system_id: "abc123" }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("displays a spinner when loading", () => {
    state.machine.items = [];

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByRole("heading", { name: /loading/i })
    ).toBeInTheDocument();
  });

  it("displays a spinner when loading the details version of the machine", () => {
    state.machine.items = [factory.machine({ system_id: "abc123" })];

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByRole("heading", { name: /loading/i })
    ).toBeInTheDocument();
  });

  it("displays an icon when locked", () => {
    state.machine.items[0].locked = true;

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(screen.getByRole("button", { name: /locked/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /locked/i })).toHaveClass(
      "has-icon"
    );
  });

  it("displays an icon when locked", () => {
    state.machine.items[0].locked = true;

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(screen.getByRole("button", { name: /locked/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /locked/i })).toHaveClass(
      "has-icon"
    );
  });

  it("displays machine status", () => {
    state.machine.items[0].status = NodeStatus.DEPLOYED;

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(screen.getByText(/deployed/i)).toBeInTheDocument();
  });

  it("displays power status when checking power", () => {
    state.machine.statuses.abc123 = factory.machineStatus({
      checkingPower: true,
    });

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(screen.getByText(/checking power/i)).toBeInTheDocument();
  });

  describe("power menu", () => {
    it("can dispatch the check power action", async () => {
      state.machine.items[0].actions = [];

      const { store } = renderWithProviders(
        <MachineHeader systemId="abc123" />,
        { state }
      );

      await userEvent.click(screen.getByRole("button", { name: /Power/i }));
      await userEvent.click(
        screen.getByRole("button", { name: /check power/i })
      );

      expect(
        store
          .getActions()
          .some((action) => action.type === "machine/checkPower")
      ).toBe(true);
    });
  });

  it("includes a tab for instances if machine has any", () => {
    state.machine.items[0] = factory.machineDetails({
      devices: [factory.machineDevice()],
      system_id: "abc123",
    });

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    expect(
      screen.getByRole("link", { name: /instances/i })
    ).toBeInTheDocument();
  });

  it("hides the subtitle when editing the name", async () => {
    state = factory.rootState({
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
        }),
      }),
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machineDetails({
            locked: false,
            permissions: ["edit"],
            system_id: "abc123",
          }),
        ],
      }),
    });

    renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("button", {
        name: new RegExp(`${state.machine.items[0].hostname}.maas`),
      })
    );
    expect(
      screen.queryByTestId("section-header-subtitle")
    ).not.toBeInTheDocument();
  });

  it("shouldn't need confirmation before locking a machine", async () => {
    state.machine.items[0].actions = [NodeActions.LOCK];
    state.machine.items[0].permissions = ["edit", "delete"];

    const { store } = renderWithProviders(<MachineHeader systemId="abc123" />, {
      state,
    });

    await userEvent.click(screen.getByRole("switch", { name: /lock/i }));

    expect(
      screen.queryByRole("complementary", {
        name: /lock/i,
      })
    ).not.toBeInTheDocument();
    const expectedAction = machineActions.lock({
      system_id: "abc123",
    });

    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });

  it("displays an error icon with configuration tab link when power type is not set and status is unknown", () => {
    state.machine.items[0].power_state = PowerState.UNKNOWN;
    state.machine.items[0].status_code = NodeStatusCode.NEW;

    renderWithProviders(<MachineHeader systemId="abc123" />, { state });

    expect(
      screen.getByRole("link", { name: /error configuration/i })
    ).toBeInTheDocument();
  });
});
