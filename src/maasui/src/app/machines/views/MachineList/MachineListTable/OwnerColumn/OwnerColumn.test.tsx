import { waitFor } from "@testing-library/react";

import { OwnerColumn } from "./OwnerColumn";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { mockUsers, usersResolvers } from "@/testing/resolvers/users";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  usersResolvers.listUsers.handler()
);

describe("OwnerColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        machineActions: factory.machineActionsState({
          data: [
            factory.machineAction({
              name: NodeActions.ACQUIRE,
              title: "Allocate...",
            }),
            factory.machineAction({
              name: NodeActions.RELEASE,
              title: "Release...",
            }),
          ],
        }),
      }),
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            actions: [],
            system_id: "abc123",
            owner: "user1",
            tags: [],
          }),
        ],
      }),
    });
  });

  it("displays owner's username", () => {
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("owner")).toHaveTextContent("user1");
  });

  it("displays owner's username if showFullName is true and user doesn't have a full name", () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ last_name: "", username: "user1" })
      )
    );
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} showFullName systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("owner")).toHaveTextContent("user1");
  });

  it("can display owner's full name if present", async () => {
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} showFullName systemId="abc123" />,
      { state }
    );

    await waitFor(() => {
      expect(screen.getByTestId("owner")).toHaveTextContent(
        mockUsers.items[0].last_name!
      );
    });
  });

  it("displays tags", () => {
    state.machine.items[0].tags = [1, 2];
    state.tag.items = [
      factory.tag({ id: 1, name: "minty" }),
      factory.tag({ id: 2, name: "aloof" }),
    ];
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );

    expect(screen.getByTestId("tags")).toHaveTextContent("aloof, minty");
  });

  it("can show a menu item to allocate a machine", async () => {
    state.machine.items[0].actions = [NodeActions.ACQUIRE];
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );
    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(
      screen.getByRole("button", { name: "Allocate..." })
    ).toBeInTheDocument();
  });

  it("can show a menu item to release a machine", async () => {
    state.machine.items[0].actions = [NodeActions.RELEASE];
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );
    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(
      screen.getByRole("button", { name: "Release..." })
    ).toBeInTheDocument();
  });

  it("can show a message when there are no menu items", async () => {
    renderWithProviders(
      <OwnerColumn onToggleMenu={vi.fn()} systemId="abc123" />,
      { state }
    );
    // Open the menu so the elements get rendered.
    await userEvent.click(screen.getByRole("button", { name: "Take action:" }));

    expect(screen.getByText("No owner actions available")).toBeInTheDocument();
  });

  it("does not render table menu if onToggleMenu not provided", () => {
    renderWithProviders(<OwnerColumn systemId="abc123" />, {
      state,
    });
    expect(
      screen.queryByRole("button", { name: "Take action:" })
    ).not.toBeInTheDocument();
  });
});
