import { Label as APIKeyFormLabels } from "../APIKeyForm/APIKeyForm";

import { APIKeyEdit, Label as APIKeyEditLabels } from "./APIKeyEdit";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("APIKeyEdit", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      token: factory.tokenState({
        items: [
          factory.token({
            id: 1,
            key: "ssh-rsa aabb",
            consumer: { key: "abc", name: "Name" },
          }),
        ],
      }),
    });
  });

  it("displays a loading component if loading", () => {
    state.token.loading = true;
    state.token.loaded = false;
    renderWithProviders(<APIKeyEdit id={1} />, { state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("handles api key not found", () => {
    state.token.items = [];
    renderWithProviders(<APIKeyEdit id={1} />, { state });
    expect(screen.getByText(APIKeyEditLabels.NotFound)).toBeInTheDocument();
  });

  it("can display an api key edit form", () => {
    renderWithProviders(<APIKeyEdit id={1} />, { state });
    const form = screen.getByRole("form", {
      name: APIKeyFormLabels.EditFormLabel,
    });
    expect(form).toBeInTheDocument();
    expect(
      within(form).getByRole("textbox", {
        name: APIKeyFormLabels.EditNameLabel,
      })
    ).toHaveValue(state.token.items[0].consumer.name);
  });
});
