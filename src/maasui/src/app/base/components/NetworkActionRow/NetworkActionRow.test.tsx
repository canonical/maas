import NetworkActionRow from "./NetworkActionRow";

import { ExpandedState } from "@/app/base/components/NodeNetworkTab/NodeNetworkTab";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  screen,
  expectTooltipOnHover,
  renderWithProviders,
} from "@/testing/utils";

describe("NetworkActionRow", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
      }),
    });
  });

  it("can include extra actions", () => {
    renderWithProviders(
      <NetworkActionRow
        extraActions={[
          {
            disabled: [[false]],
            label: "Edit",
            state: ExpandedState.EDIT,
          },
        ]}
        node={state.machine.items[0]}
      />,
      { state }
    );
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  describe("add physical", () => {
    it("disables the button when networking is disabled", async () => {
      state.machine.items[0].status = NodeStatus.DEPLOYED;

      renderWithProviders(<NetworkActionRow node={state.machine.items[0]} />, {
        state,
      });
      const addInterfaceButton = screen.getByRole("button", {
        name: "Add interface",
      });
      expect(addInterfaceButton).toBeAriaDisabled();
      await expectTooltipOnHover(
        addInterfaceButton,
        "Network can't be modified for this machine."
      );
    });
  });
});
