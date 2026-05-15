import { PowerColumn } from "./PowerColumn";

import { PowerTypeNames } from "@/app/store/general/constants";
import type { RootState } from "@/app/store/root/types";
import { PowerState } from "@/app/store/types/enum";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

describe("PowerColumn", () => {
  let state: RootState;
  let machine;
  beforeEach(() => {
    machine = factory.machine();
    machine.system_id = "abc123";
    machine.power_state = PowerState.ON;
    machine.power_type = PowerTypeNames.VIRSH;

    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [machine],
      }),
    });
  });

  it("displays the correct power state", () => {
    state.machine.items[0].power_state = PowerState.OFF;

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("power_state")).toHaveTextContent("off");
  });

  it("displays the correct power type", () => {
    state.machine.items[0].power_type = "manual";

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("power_type")).toHaveTextContent("manual");
  });

  it("can show a menu item to turn a machine on", async () => {
    state.machine.items[0].actions = [NodeActions.ON];
    state.machine.items[0].power_state = PowerState.OFF;

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );
    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(screen.getByText("Turn on")).toBeInTheDocument();
  });

  it("can show a menu item to turn a machine off", async () => {
    state.machine.items[0].actions = [NodeActions.OFF];

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(screen.getByText("Turn off")).toBeInTheDocument();
  });

  it("can show a menu item to check power", async () => {
    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(screen.getByText("Check power")).toBeInTheDocument();
  });

  it("can show a message when there are no menu items", async () => {
    state.machine.items[0].power_state = PowerState.UNKNOWN;

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(screen.getByText("No power actions available")).toBeInTheDocument();
  });

  it("does not render table menu if onToggleMenu not provided", () => {
    renderWithProviders(<PowerColumn systemId="abc123" />, {
      state,
    });

    expect(
      screen.queryByRole("button", { name: "Take action:" })
    ).not.toBeInTheDocument();
  });

  it("shows a status tooltip if machine power is in error state", async () => {
    state.machine.items[0].power_state = PowerState.ERROR;
    state.machine.items[0].status_message = "It's not working";

    renderWithProviders(
      <PowerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    await userEvent.hover(screen.getByLabelText("error"));

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("It's not working");
    });
  });
});
