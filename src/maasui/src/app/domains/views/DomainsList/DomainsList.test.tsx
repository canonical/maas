import DomainsList from "./DomainsList";

import { Labels as DomainsTableLabels } from "@/app/domains/components/DomainsTable/DomainsTable";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DomainsList", () => {
  it("correctly fetches the necessary data", () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(<DomainsList />, { state });
    const expectedActions = ["domain/fetch"];
    const actualActions = store.getActions();
    expect(
      expectedActions.every((expectedAction) =>
        actualActions.some((action) => action.type === expectedAction)
      )
    ).toBe(true);
  });

  it("shows a domains table if there are any domains", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domain({ name: "test" })],
      }),
    });
    renderWithProviders(<DomainsList />, {
      state,
    });

    expect(
      screen.getByRole("grid", { name: DomainsTableLabels.TableLable })
    ).toBeInTheDocument();
  });
});
