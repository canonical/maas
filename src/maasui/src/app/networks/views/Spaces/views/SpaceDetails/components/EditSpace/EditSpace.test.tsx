import EditSpace from "./EditSpace";

import { spaceActions } from "@/app/store/space";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

const getRootState = () =>
  factory.rootState({
    space: factory.spaceState({
      items: [
        factory.space({
          name: "outer",
          description: "The cold, dark, emptiness of space.",
        }),
      ],
      loading: false,
    }),
  });

it("dispatches an update action on submit", async () => {
  const space = factory.space({
    name: "outer",
    description: "The cold, dark, emptiness of space.",
  });
  const state = getRootState();
  state.space.items = [space];
  const { store } = renderWithProviders(
    <EditSpace handleDismiss={vi.fn()} space={space} />,
    {
      state,
    }
  );
  const spaceSummaryForm = screen.getByRole("form", {
    name: "Edit space summary",
  });
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.clear(screen.getByLabelText("Description"));
  await userEvent.type(screen.getByLabelText("Name"), "new name");
  await userEvent.type(screen.getByLabelText("Description"), "new description");
  await userEvent.click(
    within(spaceSummaryForm).getByRole("button", { name: "Save" })
  );

  await waitFor(() => {
    expect(store.getActions()).toStrictEqual([
      spaceActions.update({
        id: space.id,
        name: "new name",
        description: "new description",
      }),
    ]);
  });
});
