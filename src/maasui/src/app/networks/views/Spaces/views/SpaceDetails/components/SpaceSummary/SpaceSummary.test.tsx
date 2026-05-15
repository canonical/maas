import EditSpace from "./SpaceSummary";

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

it("displays space name and description", () => {
  const space = factory.space({
    name: "outer",
    description: "The cold, dark, emptiness of space.",
  });
  renderWithProviders(<EditSpace space={space} />);
  const spaceSummary = screen.getByRole("region", { name: "Space summary" });

  expect(within(spaceSummary).getByText("outer")).toBeInTheDocument();
  expect(
    within(spaceSummary).getByText("The cold, dark, emptiness of space.")
  ).toBeInTheDocument();
});

it("can open and close the Edit space summary form", async () => {
  const space = factory.space({
    name: "outer",
    description: "The cold, dark, emptiness of space.",
  });
  const state = getRootState();
  state.space.items = [space];
  renderWithProviders(<EditSpace space={state.space.items[0]} />, { state });
  const spaceSummary = screen.getByRole("region", { name: "Space summary" });
  await userEvent.click(
    within(spaceSummary).getAllByRole("button", { name: "Edit" })[0]
  );
  await waitFor(() => {
    expect(
      screen.getByRole("form", { name: "Edit space summary" })
    ).toBeInTheDocument();
  });

  await userEvent.click(
    within(spaceSummary).getByRole("button", { name: "Cancel" })
  );

  await waitFor(() => {
    expect(
      screen.queryByRole("form", { name: "Edit space summary" })
    ).not.toBeInTheDocument();
  });
});
