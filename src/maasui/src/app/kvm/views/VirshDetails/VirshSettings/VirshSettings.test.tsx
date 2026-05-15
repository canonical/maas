import VirshSettings from "./VirshSettings";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("VirshSettings", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        items: [factory.podDetails({ id: 1, name: "pod1" })],
        loaded: true,
      }),
      tag: factory.tagState({
        loaded: true,
      }),
    });
  });

  it("fetches the necessary data on load", () => {
    const { store } = renderWithProviders(<VirshSettings id={1} />, {
      state,
    });
    const expectedActionTypes = [
      "resourcepool/fetch",
      "tag/fetch",
      "zone/fetch",
    ];
    const actualActions = store.getActions();
    expectedActionTypes.forEach((expectedActionType) => {
      expect(
        actualActions.some(
          (actualAction) => actualAction.type === expectedActionType
        )
      );
    });
  });

  it("displays a spinner if data has not loaded", () => {
    renderWithProviders(<VirshSettings id={1} />, { state });
    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });
});
