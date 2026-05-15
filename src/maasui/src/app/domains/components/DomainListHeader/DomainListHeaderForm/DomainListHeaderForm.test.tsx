import DomainListHeaderForm, {
  Labels as DomainListHeaderFormLabels,
} from "./DomainListHeaderForm";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("DomainListHeaderForm", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState();
  });

  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<DomainListHeaderForm />, {
      state,
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls domainActions.create on save click", async () => {
    const { store } = renderWithProviders(<DomainListHeaderForm />, { state });

    await userEvent.type(
      screen.getByRole("textbox", { name: DomainListHeaderFormLabels.Name }),
      "some-domain"
    );

    await userEvent.click(
      screen.getByRole("button", {
        name: DomainListHeaderFormLabels.SubmitLabel,
      })
    );

    expect(
      store.getActions().find((action) => action.type === "domain/create")
    ).toStrictEqual({
      type: "domain/create",
      meta: {
        method: "create",
        model: "domain",
      },
      payload: {
        params: {
          authoritative: true,
          name: "some-domain",
        },
      },
    });
  });
});
