import DomainListHeader, {
  Labels as DomainListHeaderLabels,
} from "./DomainListHeader";
import DomainListHeaderForm from "./DomainListHeaderForm";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DomainListHeader", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState({
      domain: factory.domainState({
        loaded: true,
        items: [factory.domain(), factory.domain()],
      }),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("displays a loader if domains have not loaded", () => {
    const state = { ...initialState };
    state.domain.loaded = false;

    renderWithProviders(<DomainListHeader />, {
      state,
    });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays a domain count if domains have loaded", () => {
    const state = { ...initialState };
    state.domain.loaded = true;
    renderWithProviders(<DomainListHeader />, {
      state,
    });

    expect(screen.getByText("2 domains available")).toBeInTheDocument();
  });

  it("displays the form when Add domains is clicked", async () => {
    const state = { ...initialState };
    renderWithProviders(<DomainListHeader />, {
      state,
    });

    await userEvent.click(
      screen.getByRole("button", { name: DomainListHeaderLabels.AddDomains })
    );

    expect(mockOpen).toHaveBeenCalledWith({
      component: DomainListHeaderForm,
      title: "Add domains",
    });
  });
});
