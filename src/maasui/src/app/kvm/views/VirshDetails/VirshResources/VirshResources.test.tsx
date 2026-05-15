import VirshResources from "./VirshResources";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("VirshResources", () => {
  it("shows a spinner if pods have not loaded yet", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [],
        loaded: false,
      }),
    });

    renderWithProviders(<VirshResources id={1} />, {
      initialEntries: [{ pathname: "/kvm/1/project", key: "testKey" }],
      state,
    });

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});
