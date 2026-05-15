import LXDSingleResources from "./LXDSingleResources";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("LXDSingleResources", () => {
  it("shows a spinner if pods have not loaded yet", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [],
        loaded: false,
      }),
    });

    renderWithProviders(<LXDSingleResources id={1} />, {
      initialEntries: [{ pathname: "/kvm/1/project", key: "testKey" }],
      state,
    });

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});
