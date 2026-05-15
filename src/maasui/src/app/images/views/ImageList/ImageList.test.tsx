import ImageList, { Labels as ImageListLabels } from "./ImageList";

import { ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import { imageResolvers } from "@/testing/resolvers/images";
import {
  screen,
  renderWithProviders,
  setupMockServer,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  configurationsResolvers.getConfiguration.handler({
    name: ConfigNames.BOOT_IMAGES_AUTO_IMPORT,
    value: true,
  }),
  imageSourceResolvers.listImageSources.handler(),
  imageResolvers.listSelections.handler(),
  imageResolvers.listSelectionStatuses.handler(),
  imageResolvers.listSelectionStatistics.handler(),
  imageResolvers.listCustomImages.handler(),
  imageResolvers.listCustomImageStatuses.handler(),
  imageResolvers.listCustomImageStatistics.handler()
);

describe("ImageList", () => {
  it("shows a warning if automatic image sync is disabled", async () => {
    mockServer.use(
      configurationsResolvers.getConfiguration.handler({
        name: ConfigNames.BOOT_IMAGES_AUTO_IMPORT,
        value: false,
      })
    );
    renderWithProviders(<ImageList />);
    await waitForLoading();
    expect(screen.getByText(ImageListLabels.SyncDisabled)).toBeInTheDocument();
  });
});
