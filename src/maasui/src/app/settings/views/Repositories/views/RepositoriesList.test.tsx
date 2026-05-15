import { waitFor } from "@testing-library/react";

import RepositoriesList from "./RepositoriesList";

import { packageRepositoriesResolvers } from "@/testing/resolvers/packageRepositories";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  packageRepositoriesResolvers.listPackageRepositories.handler(),
  packageRepositoriesResolvers.getPackageRepository.handler()
);

describe("RepositoriesList", () => {
  it("renders 'Add PPA'", async () => {
    renderWithProviders(<RepositoriesList />);
    await userEvent.click(screen.getByRole("button", { name: "Add PPA" }));
    expect(
      screen.getByRole("complementary", { name: "Add PPA" })
    ).toBeInTheDocument();
  });

  it("renders 'Add repository'", async () => {
    renderWithProviders(<RepositoriesList />);
    await userEvent.click(
      screen.getByRole("button", { name: "Add repository" })
    );
    expect(
      screen.getByRole("complementary", { name: "Add repository" })
    ).toBeInTheDocument();
  });

  it("renders 'Edit repository'", async () => {
    renderWithProviders(<RepositoriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Edit" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Edit repository" })
    ).toBeInTheDocument();
  });

  it("renders 'Delete repository'", async () => {
    renderWithProviders(<RepositoriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Delete" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Delete repository" })
    ).toBeInTheDocument();
  });

  it("closes side panel form when canceled", async () => {
    renderWithProviders(<RepositoriesList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Delete" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Delete repository" })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("complementary", { name: "Delete repository" })
    ).not.toBeInTheDocument();
  });
});
