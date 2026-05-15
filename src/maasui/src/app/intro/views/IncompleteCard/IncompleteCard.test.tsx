import IncompleteCard, {
  Labels as IncompleteCardLabels,
} from "./IncompleteCard";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("IncompleteCard", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState();
  });

  it("renders", () => {
    renderWithProviders(<IncompleteCard />, {
      state,
    });
    expect(screen.getByText(IncompleteCardLabels.Welcome)).toBeInTheDocument();
    expect(screen.getByText(IncompleteCardLabels.Help)).toBeInTheDocument();
    expect(
      screen.getByText(IncompleteCardLabels.Incomplete)
    ).toBeInTheDocument();
  });
});
