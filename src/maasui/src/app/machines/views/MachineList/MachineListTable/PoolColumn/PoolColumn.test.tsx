import { PoolColumn } from "./PoolColumn";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { mockPools, poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const mockServer = setupMockServer(poolsResolvers.listPools.handler());

describe("PoolColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            pool: factory.modelRef({ id: 0, name: "default" }),
            description: "Firmware old",
            actions: [NodeActions.SET_POOL],
          }),
        ],
      }),
    });
  });

  it("displays pool", () => {
    state.machine.items[0].pool = factory.modelRef({ name: "pool-1" });

    renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );

    expect(screen.getByTestId("pool")).toHaveTextContent("pool-1");
  });

  it("displays description", () => {
    state.machine.items[0].description = "decomissioned";

    renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );

    expect(screen.getByTestId("note")).toHaveTextContent("decomissioned");
  });

  it("displays a message if there are no additional pools", async () => {
    mockServer.use(
      poolsResolvers.listPools.handler({ ...mockPools, items: [] })
    );
    renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Change pool:" }))
    );
    await userEvent.click(screen.getByRole("button", { name: "Change pool:" }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "No other pools available" })
      ).toBeInTheDocument();
    });
  });

  it("displays a message if the machine cannot have its pool changed", async () => {
    state.machine.items[0].actions = [];

    renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );
    await userEvent.click(screen.getByRole("button", { name: "Change pool:" }));
    expect(
      screen.getByRole("button", {
        name: "Cannot change pool of this machine",
      })
    ).toBeAriaDisabled();
  });

  it("can change pools", async () => {
    const { store } = renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );
    await waitFor(() => {
      expect(poolsResolvers.listPools.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Change pool:" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Change pool:" }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "swimming" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "swimming" }));

    expect(
      store.getActions().find((action) => action.type === "machine/setPool")
    ).toEqual({
      type: "machine/setPool",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_POOL,
          extra: {
            pool_id: 1,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("shows a spinner when changing pools", async () => {
    renderWithProviders(
      <PoolColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      {
        initialEntries: ["/machines"],
        state,
      }
    );
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Change pool:" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Change pool:" }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "swimming" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "swimming" }));
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("does not render table menu if onToggleMenu not provided", () => {
    renderWithProviders(<PoolColumn systemId="abc123" />, {
      initialEntries: ["/machines"],
      state,
    });

    expect(
      screen.queryByRole("button", { name: "Change pool:" })
    ).not.toBeInTheDocument();
  });
});
