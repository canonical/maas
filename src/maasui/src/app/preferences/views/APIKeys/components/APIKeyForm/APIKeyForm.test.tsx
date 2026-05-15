import { APIKeyForm, Label as APIKeyFormLabels } from "./APIKeyForm";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("APIKeyForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      token: factory.tokenState({
        loading: false,
        loaded: true,
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

  it("can render", () => {
    renderWithProviders(<APIKeyForm />, { state });
    expect(screen.getByRole("form", { name: APIKeyFormLabels.AddFormLabel }));
  });

  it("can create an API key", async () => {
    const { store } = renderWithProviders(<APIKeyForm />, { state });

    await userEvent.type(
      screen.getByRole("textbox", { name: APIKeyFormLabels.AddNameLabel }),
      "Token name"
    );

    await userEvent.click(
      screen.getByRole("button", { name: APIKeyFormLabels.AddSubmit })
    );

    expect(
      store.getActions().find((action) => action.type === "token/create")
    ).toStrictEqual({
      type: "token/create",
      payload: {
        params: {
          name: "Token name",
        },
      },
      meta: {
        model: "token",
        method: "create",
      },
    });
  });

  it("can update an API key", async () => {
    const { store } = renderWithProviders(
      <APIKeyForm token={state.token.items[0]} />,
      { state }
    );

    await userEvent.clear(
      screen.getByRole("textbox", { name: APIKeyFormLabels.EditNameLabel })
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: APIKeyFormLabels.EditNameLabel }),
      "New token name"
    );

    await userEvent.click(
      screen.getByRole("button", { name: APIKeyFormLabels.EditSubmit })
    );
    expect(
      store.getActions().find((action) => action.type === "token/update")
    ).toStrictEqual({
      type: "token/update",
      payload: {
        params: {
          id: 1,
          name: "New token name",
        },
      },
      meta: {
        model: "token",
        method: "update",
      },
    });
  });
});
