import { DhcpAdd } from "./DhcpAdd";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DhcpAdd", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState();
  });

  it("can render", () => {
    renderWithProviders(<DhcpAdd />, { state });

    expect(
      screen.getByRole("form", { name: "Add DHCP snippet" })
    ).toBeInTheDocument();
  });
});
