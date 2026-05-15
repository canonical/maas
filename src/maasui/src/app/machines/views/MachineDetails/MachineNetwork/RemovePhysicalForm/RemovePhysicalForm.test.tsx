import RemovePhysicalForm from "./RemovePhysicalForm";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

let state: RootState;
const nic = factory.machineInterface({
  type: NetworkInterfaceTypes.PHYSICAL,
});
beforeEach(() => {
  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machineDetails({
          system_id: "abc123",
          interfaces: [nic],
        }),
      ],
      statuses: factory.machineStatuses({
        abc123: factory.machineStatus(),
      }),
    }),
  });
});

it("renders a remove physical form", () => {
  renderWithProviders(<RemovePhysicalForm nic={nic} systemId="abc123" />, {
    state,
  });

  expect(
    screen.getByText("Are you sure you want to remove this interface?")
  ).toBeInTheDocument();
});

it("dispatches a delete interface action", async () => {
  const { store } = renderWithProviders(
    <RemovePhysicalForm nic={nic} systemId="abc123" />,
    {
      state,
    }
  );

  await userEvent.click(screen.getByRole("button", { name: "Remove" }));

  const actions = store.getActions();
  expect(
    actions.some((action) => action.type === "machine/deleteInterface")
  ).toBe(true);
  expect(
    screen.getByText("Are you sure you want to remove this interface?")
  ).toBeInTheDocument();
});
