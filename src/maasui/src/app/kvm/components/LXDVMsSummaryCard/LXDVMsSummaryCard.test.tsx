import { screen } from "@testing-library/react";

import LXDVMsSummaryCard from "./LXDVMsSummaryCard";

import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("LXDVMsSummaryCard", () => {
  it("shows a spinner if pod has not loaded yet", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [],
        loaded: false,
      }),
    });

    renderWithProviders(<LXDVMsSummaryCard id={1} />, { state });

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });
});
