import KVMDetailsHeader from "./KVMDetailsHeader";

import { screen, getTestState, renderWithProviders } from "@/testing/utils";

describe("KVMDetailsHeader", () => {
  let state: ReturnType<typeof getTestState>;

  beforeEach(() => {
    state = getTestState();
  });

  it("renders extra title blocks", () => {
    renderWithProviders(
      <KVMDetailsHeader
        tabLinks={[]}
        title="Title"
        titleBlocks={[{ title: "Title", subtitle: "Subtitle" }]}
      />,
      {
        initialEntries: ["/kvm/1"],
        state,
      }
    );
    expect(screen.getByTestId("extra-title-block")).toBeInTheDocument();
  });
});
