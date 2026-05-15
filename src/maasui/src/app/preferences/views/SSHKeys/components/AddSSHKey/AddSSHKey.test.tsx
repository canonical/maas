import { waitFor } from "@testing-library/react";

import AddSSHKey from "@/app/preferences/views/SSHKeys/components/AddSSHKey/AddSSHKey";
import { sshKeyResolvers } from "@/testing/resolvers/sshKeys";
import {
  screen,
  renderWithProviders,
  setupMockServer,
  userEvent,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  sshKeyResolvers.importSshKey.handler(),
  sshKeyResolvers.createSshKey.handler()
);
const { mockClose } = await mockSidePanel();

describe("AddSSHKey", () => {
  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<AddSSHKey />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("doesn't render 'Cancel' if intro", async () => {
    renderWithProviders(<AddSSHKey isIntro={true} />);

    expect(
      screen.queryByRole("button", { name: /Cancel/i })
    ).not.toBeInTheDocument();
  });

  it("calls the import endpoint on save button click when LP or GH is chosen", async () => {
    renderWithProviders(<AddSSHKey />);

    await userEvent.selectOptions(screen.getByRole("combobox"), "lp");

    await userEvent.type(
      screen.getByRole("textbox", { name: /Launchpad ID/i }),
      "test"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Import SSH key/i })
    );

    await waitFor(() => {
      expect(sshKeyResolvers.importSshKey.resolved).toBeTruthy();
    });
  });

  it("calls the create endpoint on save button click when Upload is chosen", async () => {
    renderWithProviders(<AddSSHKey />);

    await userEvent.selectOptions(screen.getByRole("combobox"), "upload");

    await userEvent.type(
      screen.getByRole("textbox", { name: /key/i }),
      "fake-key"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Import SSH key/i })
    );

    await waitFor(() => {
      expect(sshKeyResolvers.importSshKey.resolved).toBeTruthy();
    });
  });

  it("displays error message when import ssh key fails", async () => {
    mockServer.use(
      sshKeyResolvers.importSshKey.error({ code: 400, message: "Uh oh!" })
    );

    renderWithProviders(<AddSSHKey />);

    await userEvent.selectOptions(screen.getByRole("combobox"), "lp");

    await userEvent.type(
      screen.getByRole("textbox", { name: /Launchpad ID/i }),
      "test"
    );

    await userEvent.click(
      screen.getByRole("button", { name: /Import SSH key/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/Error/i)).toBeInTheDocument();
    });
  });
});
