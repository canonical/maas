import AddGroup from "./AddGroup";

import { groupsResolvers } from "@/testing/resolvers/groups";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(groupsResolvers.createGroup.handler());
const { mockClose } = await mockSidePanel();

describe("AddGroup", () => {
  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<AddGroup />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls create group on save click", async () => {
    renderWithProviders(<AddGroup />);

    await userEvent.type(
      screen.getByRole("textbox", { name: /group name/i }),
      "test-group"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "This is a test group"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save group/i }));

    await waitFor(() => {
      expect(groupsResolvers.createGroup.resolved).toBeTruthy();
    });
  });

  it("displays error message when create group fails", async () => {
    mockServer.use(
      groupsResolvers.createGroup.error({ code: 400, message: "Uh oh!" })
    );

    renderWithProviders(<AddGroup />);

    await userEvent.type(
      screen.getByRole("textbox", { name: /group name/i }),
      "test-group"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "This is a test group"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save group/i }));

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });

  it("prevents special characters in group name", async () => {
    renderWithProviders(<AddGroup />);

    await userEvent.type(
      screen.getByRole("textbox", { name: /group name/i }),
      "invalid/group*name"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save group/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Name cannot contain special characters")
      ).toBeInTheDocument();
    });
  });
});
