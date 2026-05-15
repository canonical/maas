import ImagesIntro, { Labels as ImagesIntroLabels } from "./ImagesIntro";

import { LONG_TIMEOUT } from "@/testing/constants";
import { configurationsResolvers } from "@/testing/resolvers/configurations";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import { imageResolvers } from "@/testing/resolvers/images";
import {
  screen,
  expectTooltipOnHover,
  renderWithProviders,
  setupMockServer,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.listImageSources.handler(),
  imageResolvers.listSelections.handler(),
  imageResolvers.listSelectionStatistics.handler(),
  imageResolvers.listSelectionStatuses.handler(),
  imageResolvers.listCustomImages.handler(),
  imageResolvers.listCustomImageStatistics.handler(),
  imageResolvers.listCustomImageStatuses.handler(),
  configurationsResolvers.getConfiguration.handler()
);

describe("ImagesIntro", () => {
  it("displays a spinner if server has not been polled yet", () => {
    renderWithProviders(<ImagesIntro />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("disables the continue button if no image and source has been configured", async () => {
    mockServer.use(
      imageSourceResolvers.listImageSources.handler({ items: [], total: 0 })
    );
    renderWithProviders(<ImagesIntro />);
    await waitForLoading();
    const button = screen.getByRole("button", {
      name: ImagesIntroLabels.Continue,
    });
    expect(button).toBeAriaDisabled();

    await expectTooltipOnHover(button, ImagesIntroLabels.CantContinue);
  });

  it("enables the continue button if an image and source has been configured", async () => {
    renderWithProviders(<ImagesIntro />);
    await waitForLoading("Loading...", { timeout: LONG_TIMEOUT });
    const button = screen.getByRole("button", {
      name: ImagesIntroLabels.Continue,
    });
    expect(button).not.toBeAriaDisabled();
  });
});
