import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import SSLKeysTable from "./SSLKeysTable";

import {
  AddSSLKey,
  DeleteSSLKey,
} from "@/app/preferences/views/SSLKeys/components";
import * as factory from "@/testing/factories";
import { sslKeyResolvers } from "@/testing/resolvers/sslKeys";
import {
  renderWithProviders,
  screen,
  waitFor,
  setupMockServer,
  mockIsPending,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(sslKeyResolvers.listSslKeys.handler());
const { mockOpen } = await mockSidePanel();

describe("SSLKeysTable", () => {
  describe("display", () => {
    it("displays a loading component if SSL keys are loading", async () => {
      mockIsPending();
      renderWithProviders(<SSLKeysTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        sslKeyResolvers.listSslKeys.handler({ items: [], total: 0 })
      );
      renderWithProviders(<SSLKeysTable />);

      await waitFor(() => {
        expect(screen.getByText("No SSL keys available.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<SSLKeysTable />);

      ["Key", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });

  describe("actions", () => {
    it("opens add SSL key side panel form", async () => {
      renderWithProviders(<SSLKeysTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Add SSL key" })
        ).toBeInTheDocument();
      });

      await userEvent.click(
        screen.getByRole("button", { name: "Add SSL key" })
      );

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddSSLKey,
        title: "Add SSL key",
      });
    });

    it("opens delete SSL key side panel form", async () => {
      mockServer.use(
        sslKeyResolvers.listSslKeys.handler({
          items: [
            factory.sslKey({
              id: 1,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<SSLKeysTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: DeleteSSLKey,
        title: "Delete SSL key",
        props: { id: 1 },
      });
    });
  });
});
