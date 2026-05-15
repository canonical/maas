import ResourceRecords, {
  Labels as ResourceRecordsLabels,
} from "./ResourceRecords";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ResourceRecords", () => {
  it("shows a message if domain has no records", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [factory.domainDetails({ id: 1, rrsets: [] })],
      }),
    });

    renderWithProviders(<ResourceRecords id={1} />, {
      state,
    });

    expect(
      screen.getByText(ResourceRecordsLabels.NoRecords)
    ).toBeInTheDocument();
  });

  it("displays a loading spinner with text when loading", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        items: [],
        loading: true,
      }),
    });
    renderWithProviders(<ResourceRecords id={1} />, {
      state,
    });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
