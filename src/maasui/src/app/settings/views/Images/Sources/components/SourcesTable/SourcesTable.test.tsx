import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import SourcesTable from "./SourcesTable";

import DeleteSource from "@/app/settings/views/Images/Sources/components/DeleteSource";
import EditSource from "@/app/settings/views/Images/Sources/components/EditSource";
import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import { imageResolvers } from "@/testing/resolvers/images";
import {
  mockIsPending,
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.listImageSources.handler(),
  imageSourceResolvers.getImageSource.handler(),
  imageSourceResolvers.fetchImageSource.handler(),
  imageSourceResolvers.createImageSource.handler(),
  imageSourceResolvers.updateImageSource.handler(),
  imageSourceResolvers.deleteImageSource.handler(),
  imageResolvers.listSelectionStatuses.handler(),
  imageResolvers.listCustomImageStatuses.handler(),
  configurationsResolvers.getConfiguration.handler({
    name: ConfigNames.BOOT_IMAGES_AUTO_IMPORT,
    value: true,
  }),
  configurationsResolvers.setConfiguration.handler()
);
const { mockOpen } = await mockSidePanel();

describe("SourcesTable", () => {
  describe("display", () => {
    it("displays a loading component if sources are loading", async () => {
      mockIsPending();
      renderWithProviders(<SourcesTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(
        imageSourceResolvers.listImageSources.handler({ items: [], total: 0 })
      );
      renderWithProviders(<SourcesTable />);

      await waitFor(() => {
        expect(screen.getByText("No sources found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<SourcesTable />);

      [
        "Name",
        "Source URL",
        "Priority",
        "Signed with GPG key",
        "Action",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("displays the row actions correctly", async () => {
      mockServer.use(
        imageSourceResolvers.listImageSources.handler({
          items: [
            factory.imageSourceFactory.build({ id: 1, enabled: true }),
            factory.imageSourceFactory.build({ id: 2, enabled: false }),
            factory.imageSourceFactory.build({
              id: 3,
              url: "http://custom.image.source/stable/",
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<SourcesTable />);
      await waitForLoading();

      const rowActions = screen.getAllByRole("button", {
        name: "Toggle menu",
      });
      expect(rowActions.length).toBe(3);

      // Default source (enabled)
      await userEvent.click(rowActions[0]);
      expect(
        screen.getByRole("button", { name: "Edit source..." })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Delete source..." })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Enable source..." })
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Disable source..." })
      ).toBeInTheDocument();
      await userEvent.click(rowActions[0]);

      // Default source (disabled)
      await userEvent.click(rowActions[1]);
      expect(
        screen.getByRole("button", { name: "Edit source..." })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Delete source..." })
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Enable source..." })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Disable source..." })
      ).not.toBeInTheDocument();
      await userEvent.click(rowActions[1]);

      // Custom source
      await userEvent.click(rowActions[2]);
      expect(
        screen.getByRole("button", { name: "Edit source..." })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Delete source..." })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Enable source..." })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Disable source..." })
      ).not.toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("opens edit source side panel form", async () => {
      mockServer.use(
        imageSourceResolvers.listImageSources.handler({
          items: [factory.imageSourceFactory.build({ id: 1 })],
          total: 1,
        })
      );

      renderWithProviders(<SourcesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Toggle menu" })
        ).toBeInTheDocument();
      });
      await userEvent.click(
        screen.getByRole("button", { name: "Toggle menu" })
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Edit source..." })
        ).toBeInTheDocument();
      });
      await userEvent.click(
        screen.getByRole("button", { name: "Edit source..." })
      );

      expect(mockOpen).toHaveBeenCalledWith({
        component: EditSource,
        title: "Edit default source",
        props: { id: 1, isDefault: true },
      });
    });

    it("opens delete source side panel form", async () => {
      mockServer.use(
        imageSourceResolvers.listImageSources.handler({
          items: [
            factory.imageSourceFactory.build({
              id: 1,
              url: "http://custom.image.source/stable/",
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<SourcesTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Toggle menu" })
        ).toBeInTheDocument();
      });
      await userEvent.click(
        screen.getByRole("button", { name: "Toggle menu" })
      );

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete source..." })
        ).toBeInTheDocument();
      });
      await userEvent.click(
        screen.getByRole("button", { name: "Delete source..." })
      );

      expect(mockOpen).toHaveBeenCalledWith({
        component: DeleteSource,
        title: "Delete custom source",
        props: { id: 1 },
      });
    });
  });
});
