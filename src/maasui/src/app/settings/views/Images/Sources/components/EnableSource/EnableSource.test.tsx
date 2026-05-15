import { expect, it } from "vitest";

import EnableSource from "@/app/settings/views/Images/Sources/components/EnableSource/EnableSource";
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
      enabled: false,
    })
  ),
  imageSourceResolvers.updateImageSource.handler()
);
const { mockClose } = await mockSidePanel();

describe("EnableSource", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<EnableSource id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls update source on save click", async () => {
    renderWithProviders(<EnableSource id={1} />);
    await waitForLoading();

    await userEvent.click(
      screen.getByRole("button", { name: "Enable source" })
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
    renderWithProviders(<EnableSource id={1} />);
    await waitForLoading();

    await userEvent.click(
      screen.getByRole("button", { name: "Enable source" })
    );
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
