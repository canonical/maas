import EditGroup from "./EditGroup";

import { groupsResolvers } from "@/testing/resolvers/groups";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  waitFor,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  groupsResolvers.updateGroup.handler(),
  groupsResolvers.getGroup.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditGroup", () => {
  const testGroupId = 1;
  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<EditGroup id={testGroupId} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls edit group on save click", async () => {
    renderWithProviders(<EditGroup id={testGroupId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Group name")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Group name"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /group name/i }),
      "new-test-group"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save group/i }));

    await waitFor(() => {
      expect(groupsResolvers.updateGroup.resolved).toBeTruthy();
    });
  });

  it("displays error message when edit group fails", async () => {
    mockServer.use(
      groupsResolvers.updateGroup.error({ code: 400, message: "Uh oh!" })
    );

    renderWithProviders(<EditGroup id={testGroupId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Group name")).toBeInTheDocument();
    });

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
});
