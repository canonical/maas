import AppSideNavigation from "./AppSideNavigation";

import urls from "@/app/base/urls";
import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import { statusActions } from "@/app/store/status";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

const mockUseNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual: object = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockUseNavigate,
  };
});

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(
    factory.user({ is_superuser: true, id: 1 })
  ),
  authResolvers.getMeStatistics.handler(
    factory.userStatistics({ id: 1, completed_intro: true })
  )
);

afterEach(() => {
  vi.resetModules();
  vi.resetAllMocks();
});

describe("GlobalSideNav", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.COMPLETED_INTRO, value: true }),
        ],
        loaded: true,
      }),
      controller: factory.controllerState({
        items: [factory.controller()],
        loaded: true,
      }),
      pod: factory.podState({
        loaded: true,
        items: [
          factory.pod({
            type: "virsh",
          }),
        ],
      }),
    });
  });

  it("displays navigation", () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });

    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("can handle a logged out user", () => {
    mockServer.use(authResolvers.getCurrentUser.error({}));
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });

    const primaryNavigation = screen.getByRole("banner", {
      name: "main navigation",
    });
    expect(within(primaryNavigation).getAllByRole("link")).toHaveLength(1);
    expect(
      within(primaryNavigation).getAllByRole("link")[0]
    ).toHaveAccessibleName("Homepage");
    expect(
      within(primaryNavigation).queryByRole("list")
    ).not.toBeInTheDocument();
  });

  it("can dispatch an action to log out", async () => {
    const { store } = renderWithProviders(<AppSideNavigation />, { state });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Log out" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    const expectedAction = statusActions.logout();
    await waitFor(() => {
      expect(
        store.getActions().find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("hides nav links if not completed intro", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({
          username: "koala",
        })
      ),
      authResolvers.getMeStatistics.handler(
        factory.userStatistics({
          completed_intro: false,
        })
      )
    );
    renderWithProviders(<AppSideNavigation />, {
      state,
    });

    const mainNav = screen.getByRole("banner", { name: "main navigation" });
    await waitFor(() => {
      expect(mainNav).toBeInTheDocument();
    });
    expect(within(mainNav).getAllByRole("link")[0]).toHaveAccessibleName(
      "Homepage"
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Log out" })
      ).toBeInTheDocument();
    });
  });

  it("can highlight active URL", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/settings"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Settings");
  });

  it("highlights machines when active", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machines"],
      state,
    });

    await waitFor(() => {
      expect(screen.getAllByRole("navigation")).not.toHaveLength(0);
    });
    // Ensure that machine link is selected from within the nav
    const sideNavigation = screen.getAllByRole("navigation")[0];
    await waitFor(() => {
      expect(
        within(sideNavigation).getAllByRole("link", { current: "page" }).length
      ).toBeGreaterThan(0);
    });
    const currentMenuItem = within(sideNavigation).getAllByRole("link", {
      current: "page",
    })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Machines");
  });

  it("highlights pools when active", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/pools"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Pools");
  });

  it("highlights tags when active", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/tags"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Tags");
  });

  it("highlights tags viewing a tag", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/tag/1"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Tags");
  });

  it("can highlight a url with a query param", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/networks/subnets?by=fabric"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Networks");
  });

  it("highlights sub-urls", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machine/abc123"],
      state,
    });

    await waitFor(() => {
      expect(screen.getByRole("link", { current: "page" })).toBeInTheDocument();
    });
    const currentMenuItem = screen.getAllByRole("link", { current: "page" })[0];
    expect(currentMenuItem).toBeInTheDocument();
    expect(currentMenuItem).toHaveTextContent("Machines");
  });

  it("displays a warning icon next to controllers if vault is not fully configured", async () => {
    state.controller.items = [
      factory.controller({ vault_configured: true }),
      factory.controller({ vault_configured: false }),
    ];
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /Controllers/i })
      ).toBeInTheDocument();
    });
    const controllerLink = screen.getByRole("link", {
      name: /Controllers/i,
    });
    const warningIcon = within(controllerLink).getByTestId("warning-icon");
    expect(warningIcon).toHaveClass("p-icon--security-warning-grey");
  });

  it("does not display a warning icon next to controllers if vault is fully configured", async () => {
    state.controller.items = [
      factory.controller({ vault_configured: true }),
      factory.controller({ vault_configured: true }),
    ];
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /Controllers/i })
      ).toBeInTheDocument();
    });
    const controllerLink = screen.getByRole("link", {
      name: "Controllers",
    });
    expect(
      within(controllerLink).queryByTestId("warning-icon")
    ).not.toBeInTheDocument();
  });

  it("does not display a warning icon next to controllers if vault setup has not started", async () => {
    state.controller.items = [
      factory.controller({ vault_configured: false }),
      factory.controller({ vault_configured: false }),
    ];
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });
    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /Controllers/i })
      ).toBeInTheDocument();
    });
    const controllerLink = screen.getByRole("link", {
      name: "Controllers",
    });
    expect(
      within(controllerLink).queryByTestId("warning-icon")
    ).not.toBeInTheDocument();
  });

  it("links from the logo to machine list page for admins", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machine/abc123"],
      state,
    });
    await waitFor(() => {
      expect(authResolvers.getCurrentUser.resolved).toBe(true);
    });
    expect(
      within(screen.getByRole("banner", { name: "main navigation" })).getByRole(
        "link",
        {
          name: "Homepage",
        }
      )
    ).toHaveAttribute("href", "/machines");
  });

  it("links from the logo to the machine list for non admins", async () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: false })
      )
    );
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machine/abc123"],
      state,
    });
    await waitFor(() => {
      expect(authResolvers.getCurrentUser.resolved).toBe(true);
    });
    expect(
      within(screen.getByRole("banner", { name: "main navigation" })).getByRole(
        "link",
        {
          name: "Homepage",
        }
      )
    ).toHaveAttribute("href", "/machines");
    expect(
      within(screen.getByRole("banner", { name: "main navigation" })).getByRole(
        "link",
        {
          name: "Homepage",
        }
      )
    ).toHaveAttribute("href", "/machines");
  });

  it("does not redirect if the intro is being displayed", async () => {
    state.config.items = [
      factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
    ];

    const { router } = renderWithProviders(<AppSideNavigation />, {
      state,
      initialEntries: [urls.intro.images],
    });
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(urls.intro.images);
    });
  });

  it("displays 'Virsh' link if user has Virsh KVM hosts", async () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machines"],
      state,
    });
    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Virsh/i })).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Virsh" })).toBeInTheDocument();
  });

  it("hides 'Virsh' link if user has no Virsh KVM hosts", () => {
    state.pod.items = [];
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/machines"],
      state,
    });

    expect(
      screen.queryByRole("link", { name: "Virsh" })
    ).not.toBeInTheDocument();
  });

  it("is collapsed by default", () => {
    renderWithProviders(<AppSideNavigation />, {
      initialEntries: ["/"],
      state,
    });

    expect(screen.getByRole("banner", { name: "main navigation" })).toHaveClass(
      "is-collapsed"
    );
  });

  it("persists collapsed state", async () => {
    const { rerender } = renderWithProviders(<AppSideNavigation />, {
      state,
    });

    const primaryNavigation = screen.getByRole("banner", {
      name: "main navigation",
    });
    await userEvent.click(
      screen.getByRole("button", { name: "expand main navigation" })
    );
    expect(primaryNavigation).toHaveClass("is-pinned");
    rerender(<AppSideNavigation />);
    expect(primaryNavigation).toHaveClass("is-pinned");
  });
});
