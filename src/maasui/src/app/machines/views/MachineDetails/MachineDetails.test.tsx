import { waitFor } from "@testing-library/react";
import type { Mock } from "vitest";

import MachineDetails from "./MachineDetails";

import urls from "@/app/base/urls";
import { useFetchMachine } from "@/app/store/machine/utils/hooks";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

vi.mock("@/app/store/machine/utils/hooks", async () => ({
  ...(await vi.importActual("@/app/store/machine/utils/hooks")),
  useFetchMachine: vi.fn(),
}));

describe("MachineDetails", () => {
  let state: RootState;
  let scrollToSpy: Mock;

  beforeEach(() => {
    scrollToSpy = vi.fn();
    global.scrollTo = scrollToSpy;
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            fqdn: "test-machine",
            system_id: "abc123",
            devices: [factory.machineDevice()],
          }),
        ],
        loaded: true,
      }),
    });
    vi.mocked(useFetchMachine).mockReturnValue({
      machine: factory.machineDetails({
        fqdn: "test-machine",
        system_id: "abc123",
      }),
      loaded: true,
      loading: false,
      error: null,
    });
  });

  afterAll(() => {
    vi.restoreAllMocks();
  });

  it("dispatches an action to set the machine as active", () => {
    const { store } = renderWithProviders(<MachineDetails />, {
      state,
      initialEntries: [urls.machines.machine.summary({ id: "abc123" })],
      pattern: `${urls.machines.machine.index(null)}/*`,
    });

    expect(
      store.getActions().find((action) => action.type === "machine/setActive")
    ).toEqual({
      meta: {
        method: "set_active",
        model: "machine",
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
      type: "machine/setActive",
    });
  });

  it("displays a message if the machine does not exist", () => {
    vi.mocked(useFetchMachine).mockReturnValue({
      machine: null,
      loaded: false,
      loading: false,
      error: "Uh oh!",
    });
    renderWithProviders(<MachineDetails />, {
      initialEntries: [urls.machines.machine.summary({ id: "not-valid-id" })],
      pattern: `${urls.machines.machine.index(null)}/*`,
      state,
    });
    expect(screen.getByTestId("not-found")).toBeInTheDocument();
  });

  it("cleans up when unmounting", () => {
    const {
      result: { unmount },
      store,
    } = renderWithProviders(<MachineDetails />, {
      state,
      initialEntries: [urls.machines.machine.summary({ id: "abc123" })],
      pattern: `${urls.machines.machine.index(null)}/*`,
    });
    unmount();
    expect(
      store.getActions().some((action) => action.type === "machine/cleanup")
    ).toBe(true);
  });

  it("scrolls to the top when changing tabs", async () => {
    renderWithProviders(<MachineDetails />, {
      state,
      initialEntries: [urls.machines.machine.summary({ id: "abc123" })],
      pattern: `${urls.machines.machine.index(null)}/*`,
    });

    const linkTo = screen.getByRole("link", { name: "USB" });
    await userEvent.click(linkTo);
    await waitFor(() => {
      expect(scrollToSpy).toHaveBeenCalled();
    });
  });
});
