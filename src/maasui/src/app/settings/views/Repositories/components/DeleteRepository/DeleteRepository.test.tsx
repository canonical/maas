import DeleteRepository from "./DeleteRepository";

import { packageRepositoriesResolvers } from "@/testing/resolvers/packageRepositories";
import {
  screen,
  renderWithProviders,
  userEvent,
  setupMockServer,
  waitFor,
  waitForLoading,
  mockSidePanel,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

const mockServer = setupMockServer(
  packageRepositoriesResolvers.getPackageRepository.handler(),
  packageRepositoriesResolvers.deletePackageRepository.handler()
);

describe("RepositoryDelete", () => {
  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<DeleteRepository id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("can delete a repository and close the side panel", async () => {
    renderWithProviders(<DeleteRepository id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(
        packageRepositoriesResolvers.deletePackageRepository.resolved
      ).toBe(true);
    });
  });

  it("shows errors on submission", async () => {
    mockServer.use(
      packageRepositoriesResolvers.deletePackageRepository.error()
    );
    renderWithProviders(<DeleteRepository id={1} />);
    await waitForLoading();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.getByText(/Error/)).toBeInTheDocument();
    });
  });
});
