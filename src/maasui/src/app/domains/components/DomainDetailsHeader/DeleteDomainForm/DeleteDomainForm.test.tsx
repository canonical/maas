import DeleteDomainForm, {
  Labels as DeleteDomainFormLabels,
} from "./DeleteDomainForm";

import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("DeleteDomainForm", () => {
  it("calls closeForm on cancel click", async () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ id: 1, name: "domain-in-the-brain" })],
      }),
    });
    renderWithProviders(<DeleteDomainForm id={1} />, {
      state,
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("shows the correct text if the domain is deletable and dispatches the correct action when delete is clicked", async () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domain({
            id: 1,
            name: "domain-in-the-brain",
            resource_count: 0,
          }),
        ],
      }),
    });

    const { store } = renderWithProviders(<DeleteDomainForm id={1} />, {
      state,
    });

    expect(
      screen.getByText(DeleteDomainFormLabels.AreYouSure)
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: DeleteDomainFormLabels.DeleteLabel })
    );

    expect(
      store.getActions().find((action) => action.type === "domain/delete")
    ).toStrictEqual({
      type: "domain/delete",
      meta: {
        method: "delete",
        model: "domain",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("shows the correct text and disables the delete button if the domain has resource records", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domain({
            id: 1,
            name: "domain-in-the-brain",
            resource_count: 12,
          }),
        ],
      }),
    });

    renderWithProviders(<DeleteDomainForm id={1} />, {
      state,
    });

    expect(
      screen.getByText(DeleteDomainFormLabels.CannotDelete)
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: DeleteDomainFormLabels.DeleteLabel })
    ).toBeDisabled();
  });
});
