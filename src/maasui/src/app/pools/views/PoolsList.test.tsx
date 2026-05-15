import { waitFor } from "@testing-library/react";

import PoolsList from "@/app/pools/views/PoolsList";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  screen,
  userEvent,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(
  poolsResolvers.listPools.handler(),
  poolsResolvers.getPool.handler()
);

describe("PoolsList", () => {
  it("renders AddPool", async () => {
    renderWithProviders(<PoolsList />);
    await userEvent.click(screen.getByRole("button", { name: "Add pool" }));
    expect(
      screen.getByRole("complementary", { name: "Add pool" })
    ).toBeInTheDocument();
  });

  it("renders EditPool when a valid poolId is provided", async () => {
    renderWithProviders(<PoolsList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Edit" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[2]);
    expect(
      screen.getByRole("complementary", { name: "Edit pool" })
    ).toBeInTheDocument();
  });

  it("renders DeletePool when a valid poolId is provided", async () => {
    renderWithProviders(<PoolsList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Delete" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[2]);
    expect(
      screen.getByRole("complementary", { name: "Delete pool" })
    ).toBeInTheDocument();
  });

  it("closes side panel form when canceled", async () => {
    renderWithProviders(<PoolsList />);
    await userEvent.click(screen.getByRole("button", { name: "Add pool" }));
    expect(
      screen.getByRole("complementary", { name: "Add pool" })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("complementary", { name: "Add pool" })
    ).not.toBeInTheDocument();
  });
});
