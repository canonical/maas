import ReleaseForm from "./ReleaseForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("ReleaseForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loaded: true,
        items: [
          factory.config({
            name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
            value: false,
          }),
          factory.config({
            name: ConfigNames.DISK_ERASE_WITH_SECURE_ERASE,
            value: false,
          }),
          factory.config({
            name: ConfigNames.DISK_ERASE_WITH_QUICK_ERASE,
            value: false,
          }),
        ],
      }),
      machine: factory.machineState({
        items: [
          factory.machine({ system_id: "abc123" }),
          factory.machine({ system_id: "def456" }),
        ],
        statuses: {
          abc123: factory.machineStatus({ releasing: false }),
          def456: factory.machineStatus({ releasing: false }),
        },
      }),
    });
  });

  it("sets the initial disk erase behaviour from global config", () => {
    state.machine.selected = { items: ["abc123", "def456"] };
    state.config.items = [
      factory.config({
        name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
        value: true,
      }),
      factory.config({
        name: ConfigNames.DISK_ERASE_WITH_SECURE_ERASE,
        value: false,
      }),
      factory.config({
        name: ConfigNames.DISK_ERASE_WITH_QUICK_ERASE,
        value: true,
      }),
    ];
    renderWithProviders(<ReleaseForm isViewingDetails={false} />, { state });

    expect(
      screen.getByRole("checkbox", { name: "Erase disks before releasing" })
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Use secure erase" })
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Use quick erase (not secure)" })
    ).toBeChecked();
  });

  it("correctly dispatches action to release given machines", async () => {
    state.machine.selected = { items: ["abc123", "def456"] };
    const { store } = renderWithProviders(
      <ReleaseForm isViewingDetails={false} />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("checkbox", { name: "Erase disks before releasing" })
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: "Use secure erase" })
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Release 2 machines" })
    );

    expect(
      store.getActions().filter((action) => action.type === "machine/release")
    ).toMatchObject([
      {
        type: "machine/release",
        meta: {
          model: "machine",
          method: "action",
        },
        payload: {
          params: {
            action: NodeActions.RELEASE,
            extra: {
              erase: true,
              quick_erase: false,
              secure_erase: true,
            },
            system_id: undefined,
            filter: {
              id: ["abc123", "def456"],
            },
          },
        },
      },
    ]);
  });
});
