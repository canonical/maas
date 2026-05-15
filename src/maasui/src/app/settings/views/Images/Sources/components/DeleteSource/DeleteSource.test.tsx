import DeleteSource from "./DeleteSource";

import { imageSourceResolvers } from "@/testing/resolvers/imageSources";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
  waitForLoading,
} from "@/testing/utils";

const mockServer = setupMockServer(
  imageSourceResolvers.getImageSource.handler(),
  imageSourceResolvers.deleteImageSource.handler()
);
const { mockClose } = await mockSidePanel();

describe("DeleteSource", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(<DeleteSource id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete source on save click", async () => {
    renderWithProviders(<DeleteSource id={1} />);
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete source" })
    );
    await waitFor(() => {
      expect(imageSourceResolvers.deleteImageSource.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete source fails", async () => {
    mockServer.use(
      imageSourceResolvers.deleteImageSource.error({
        code: 400,
        message: "Uh oh!",
      })
    );
    renderWithProviders(<DeleteSource id={1} />);
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete source" })
    );
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
