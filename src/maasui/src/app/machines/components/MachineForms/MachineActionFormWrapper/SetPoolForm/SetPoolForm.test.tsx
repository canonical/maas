import SetPoolForm from "./SetPoolForm";

import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

setupMockServer(
  poolsResolvers.listPools.handler(),
  poolsResolvers.createPool.handler()
);

describe("SetPoolForm", () => {
  let state: RootState;
  const machines = [
    factory.machine({
      system_id: "abc123",
    }),
    factory.machine({
      system_id: "def456",
    }),
  ];
  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
    state = factory.rootState({
      machine: factory.machineState({
        errors: {},
        loading: false,
        loaded: true,
        items: machines,
        selected: {
          items: machines.map((machine) => machine.system_id),
        },
        statuses: {
          abc123: factory.machineStatus({ settingPool: false }),
          def456: factory.machineStatus({ settingPool: false }),
        },
      }),
    });
  });

  it("correctly dispatches actions to set pools of selected machines", async () => {
    const { store } = renderWithProviders(
      <SetPoolForm isViewingDetails={false} />,
      {
        state,
      }
    );

    await waitFor(() => {
      expect(
        screen.getByRole("combobox", {
          name: "Resource pool",
        })
      ).toBeInTheDocument();
    });

    const poolSelection = screen.getByRole("combobox", {
      name: "Resource pool",
    });
    await userEvent.selectOptions(poolSelection, "swimming");

    const confirmButton = screen.getByRole("button", {
      name: /Set pool/i,
    });
    await userEvent.click(confirmButton);

    expect(
      store.getActions().filter((action) => action.type === "machine/setPool")
    ).toStrictEqual([
      {
        meta: {
          callId: undefined,
          method: "action",
          model: "machine",
        },
        payload: {
          params: {
            action: NodeActions.SET_POOL,
            extra: {
              pool_id: 1,
            },
            filter: {
              id: ["abc123", "def456"],
            },
            system_id: undefined,
          },
        },
        type: "machine/setPool",
      },
    ]);
  });

  it("correctly dispatches action to create and set pool of selected machines", async () => {
    const { store } = renderWithProviders(
      <SetPoolForm isViewingDetails={false} />,
      {
        state,
      }
    );

    await waitFor(() => {
      expect(
        screen.getByRole("radio", { name: "Create pool" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("radio", { name: "Create pool" }));

    const nameInput = screen.getByRole("textbox", { name: "Name" });
    await userEvent.type(nameInput, "pool-1");

    const confirmButton = screen.getByRole("button", {
      name: /Set pool/i,
    });
    await userEvent.click(confirmButton);

    expect(poolsResolvers.createPool.resolved).toBe(true);

    expect(
      store.getActions().filter((action) => action.type === "machine/setPool")
    ).toStrictEqual([
      {
        meta: {
          callId: undefined,
          method: "action",
          model: "machine",
        },
        payload: {
          params: {
            action: NodeActions.SET_POOL,
            extra: {
              pool_id: 1,
            },
            filter: {
              id: ["abc123", "def456"],
            },
            system_id: undefined,
          },
        },
        type: "machine/setPool",
      },
    ]);
  });
});
