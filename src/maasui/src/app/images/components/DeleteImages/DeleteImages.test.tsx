import DeleteImages from "./DeleteImages";

import { imageResolvers } from "@/testing/resolvers/images";
import {
  userEvent,
  screen,
  mockSidePanel,
  renderWithProviders,
  setupMockServer,
  waitForLoading,
  waitFor,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();
const mockServer = setupMockServer(
  imageResolvers.listSelections.handler(),
  imageResolvers.deleteSelections.handler(),
  imageResolvers.deleteCustomImages.handler()
);

describe("DeleteImages", () => {
  it("calls closeForm on cancel click", async () => {
    renderWithProviders(
      <DeleteImages rowSelection={{}} setRowSelection={vi.fn} />
    );
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls delete images on save click", async () => {
    renderWithProviders(
      <DeleteImages
        rowSelection={{ "1-selection": true, "2-custom": true }}
        setRowSelection={vi.fn}
      />
    );
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    await waitFor(() => {
      expect(imageResolvers.deleteSelections.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(imageResolvers.deleteCustomImages.resolved).toBeTruthy();
    });
  });

  it("displays error messages when delete image fails", async () => {
    mockServer.use(
      imageResolvers.deleteSelections.error({ code: 400, message: "Uh oh!" })
    );
    renderWithProviders(
      <DeleteImages
        rowSelection={{ "1-selection": true }}
        setRowSelection={vi.fn}
      />
    );
    await waitForLoading();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete 1 image" })
    );
    await waitFor(() => {
      expect(screen.getByText(/Uh oh!/i)).toBeInTheDocument();
    });
  });
});
