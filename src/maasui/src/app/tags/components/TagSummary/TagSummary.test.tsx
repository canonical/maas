import TagSummary from "./TagSummary";

import type { RootState } from "@/app/store/root/types";
import { tagActions } from "@/app/store/tag";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    tag: factory.tagState({
      items: [
        factory.tag({
          id: 1,
          name: "rad",
        }),
        factory.tag({
          id: 2,
          name: "cool",
        }),
      ],
    }),
  });
});

it("dispatches actions to fetch necessary data", () => {
  const { store } = renderWithProviders(<TagSummary id={1} />, { state });

  const expectedActions = [tagActions.fetch()];
  const actualActions = store.getActions();
  expectedActions.forEach((expectedAction) => {
    expect(
      actualActions.find(
        (actualAction) => actualAction.type === expectedAction.type
      )
    ).toStrictEqual(expectedAction);
  });
});

it("displays a message if the tag does not exist", () => {
  const state = factory.rootState({
    tag: factory.tagState({
      items: [],
      loading: false,
    }),
  });
  renderWithProviders(<TagSummary id={1} />, { state });

  expect(screen.getByText("Tag not found")).toBeInTheDocument();
});

it("shows a spinner if the tag has not loaded yet", () => {
  const state = factory.rootState({
    tag: factory.tagState({
      items: [],
      loading: true,
    }),
  });
  renderWithProviders(<TagSummary id={1} />, { state });

  expect(screen.getByTestId("Spinner")).toBeInTheDocument();
});

it("displays the tag name when not narrow", () => {
  renderWithProviders(<TagSummary id={1} />, { state });
  expect(screen.getByText("rad")).toBeInTheDocument();
});

it("does not display the tag name when narrow", () => {
  renderWithProviders(<TagSummary id={1} narrow />, { state });
  expect(screen.queryByText("rad")).not.toBeInTheDocument();
});
