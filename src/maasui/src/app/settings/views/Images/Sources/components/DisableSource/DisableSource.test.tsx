import { expect, it } from "vitest";

import DisableSource from "@/app/settings/views/Images/Sources/components/DisableSource/DisableSource";
import { imageSourceFactory } from "@/testing/factories";
import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import {
  userEvent,
  renderWithProviders,
  screen,
  waitForLoading,
  waitFor,
  setupMockServer,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.fetchImageSource.handler(),
  imageSourceResolvers.getImageSource.handler(
    imageSourceFactory.build({
      id: 1,
      enabled: true,
    })
  ),
  imageSourceResolvers.updateImageSource.handler()
);
const { mockClose } = await mockSidePanel();

describe("DisableSource", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<DisableSource id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls update source on save click", async () => {
    renderWithProviders(<DisableSource id={1} />);
    await waitForLoading();

    await userEvent.click(
      screen.getByRole("button", { name: "Disable source" })
    );
    await waitFor(() => {
      expect(imageSourceResolvers.updateImageSource.resolved).toBeTruthy();
    });
  });

  it("displays error messages when update source fails", async () => {
    mockServer.use(
      imageSourceResolvers.updateImageSource.error({
        code: 400,
        message: "Uh oh!",
      })
    );
    renderWithProviders(<DisableSource id={1} />);
    await waitForLoading();

    await userEvent.click(
      screen.getByRole("button", { name: "Disable source" })
    );
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
