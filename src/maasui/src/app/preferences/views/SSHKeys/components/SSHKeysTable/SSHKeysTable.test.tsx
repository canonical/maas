import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import SSHKeysTable from "./SSHKeysTable";

import {
  AddSSHKey,
  DeleteSSHKey,
} from "@/app/preferences/views/SSHKeys/components";
import * as factory from "@/testing/factories";
import { sshKeyResolvers } from "@/testing/resolvers/sshKeys";
import {
  renderWithProviders,
  screen,
  waitFor,
  setupMockServer,
  mockIsPending,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(sshKeyResolvers.listSshKeys.handler());
const { mockOpen } = await mockSidePanel();

describe("SSHKeysTable", () => {
  describe("display", () => {
    it("displays a loading component if SSH keys are loading", async () => {
      mockIsPending();
      renderWithProviders(<SSHKeysTable isIntro={false} />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        sshKeyResolvers.listSshKeys.handler({ items: [], total: 0 })
      );
      renderWithProviders(<SSHKeysTable isIntro={false} />);

      await waitFor(() => {
        expect(screen.getByText("No SSH keys available.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<SSHKeysTable isIntro={false} />);

      ["Source", "ID", "Key", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });

  describe("permissions", () => {
    it.skip("enables the action buttons with correct permissions");

    it.skip("disables the action buttons without permissions");
  });

  describe("actions", () => {
    it("opens add SSH key side panel form", async () => {
      renderWithProviders(<SSHKeysTable isIntro={false} />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Import SSH key" })
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: "Import SSH key" })
      );

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddSSHKey,
        title: "Add SSH key",
      });
    });

    it("opens delete SSH key side panel form", async () => {
      mockServer.use(
        sshKeyResolvers.listSshKeys.handler({
          items: [
            factory.sshKey({
              id: 1,
            }),
            factory.sshKey({
              id: 2,
            }),
          ],
          total: 2,
        })
      );

      renderWithProviders(<SSHKeysTable isIntro={false} />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: DeleteSSHKey,
        title: "Delete SSH keys",
        props: { ids: [1, 2] },
      });
    });
  });
});
