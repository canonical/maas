import Sources from "@/app/settings/views/Images/Sources/Sources";
import AddSource from "@/app/settings/views/Images/Sources/components/AddSource";
import { ConfigNames } from "@/app/store/config/types";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import { imageResolvers } from "@/testing/resolvers/images";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
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

describe("Sources", () => {
  it("opens add source side panel form", async () => {
    renderWithProviders(<Sources />);

    await userEvent.click(
      screen.getByRole("button", { name: "Add custom source" })
    );

    expect(mockOpen).toHaveBeenCalledWith({
      component: AddSource,
      title: "Add custom source",
    });
  });
});
