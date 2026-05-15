import DomainDetails from "./DomainDetails";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DomainDetails", () => {
  it("renders 'Not Found' header if domains loaded and domain not found", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [],
        loading: false,
      }),
    });
    renderWithProviders(<DomainDetails />, {
      state,
    });

    expect(screen.getByText("Domain not found")).toBeInTheDocument();
  });
});
