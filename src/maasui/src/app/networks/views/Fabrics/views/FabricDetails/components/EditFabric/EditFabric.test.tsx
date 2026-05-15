import EditFabric from "./EditFabric";

import { fabricActions } from "@/app/store/fabric";
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
    fabric: factory.fabricState({
      items: [
        factory.fabric({
          name: "fabric-1",
          description: "fabric-1 description",
        }),
      ],
      loading: false,
    }),
  });

it("dispatches an update action on submit", async () => {
  const fabric = factory.fabric({
    name: "fabric-1",
    description: "fabric-1 description",
  });
  const state = getRootState();
  state.fabric.items = [fabric];
  const { store } = renderWithProviders(
    <EditFabric handleDismiss={vi.fn()} id={fabric.id} />,
    { state }
  );
  const EditSummaryForm = screen.getByRole("form", {
    name: "Edit fabric summary",
  });
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.clear(screen.getByLabelText("Description"));
  await userEvent.type(screen.getByLabelText("Name"), "new name");
  await userEvent.type(screen.getByLabelText("Description"), "new description");
  await userEvent.click(
    within(EditSummaryForm).getByRole("button", { name: "Save summary" })
  );

  const expectedAction = fabricActions.update({
    id: fabric.id,
    name: "new name",
    description: "new description",
  });
  await waitFor(() => {
    expect(
      store.getActions().find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
