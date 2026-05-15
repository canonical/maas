import userEvent from "@testing-library/user-event";
import { describe } from "vitest";

import PoolsTable from "./PoolsTable";

import { DeletePool, EditPool } from "@/app/pools/components";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  screen,
  waitFor,
  setupMockServer,
  within,
  mockIsPending,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  poolsResolvers.listPools.handler(),
  poolsResolvers.getPool.handler()
);
const { mockOpen } = await mockSidePanel();

describe("PoolsTable", () => {
  describe("display", () => {
    it("displays a loading component if pools are loading", async () => {
      mockIsPending();
      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      mockServer.use(poolsResolvers.listPools.handler({ items: [], total: 0 }));
      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(screen.getByText("No pools found.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<PoolsTable />);

      ["Name", "Machines", "Description", "Action"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("does not show a machine link for empty pools", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({ name: "default", machine_total_count: 0 }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByText("Empty pool")
        ).toBeInTheDocument();
      });
    });

    it("can show a machine link for non-empty pools", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({
              name: "default",
              machine_total_count: 5,
              machine_ready_count: 1,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          within(
            screen.getByRole("row", {
              name: new RegExp(`^default`, "i"),
            })
          ).getByRole("link", { name: "1 of 5 ready" })
        ).toHaveAttribute("href", "/machines?pool=%3Ddefault");
      });
    });
  });

  describe("permissions", () => {
    it("enables the action buttons with correct permissions", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({
              machine_ready_count: 0,
              machine_total_count: 0,
              permissions: ["edit", "delete"],
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Edit" })).not.toHaveClass(
          "is-disabled"
        );
      });
      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Delete" })).not.toHaveClass(
          "is-disabled"
        );
      });
    });

    it("disables the action buttons without permissions", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [factory.resourcePool({ permissions: [] })],
          total: 1,
        })
      );
      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Edit" })).toHaveClass(
          "is-disabled"
        );
      });

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Delete" })).toHaveClass(
          "is-disabled"
        );
      });
    });

    it("disables the delete button for default pools", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({
              id: 0,
              name: "default",
              description: "default",
              is_default: true,
              permissions: ["edit", "delete"],
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeAriaDisabled();
      });
    });

    it("disables the delete button for pools that contain machines", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({
              id: 0,
              name: "machines",
              description: "has machines",
              is_default: false,
              permissions: ["edit", "delete"],
              machine_total_count: 1,
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeAriaDisabled();
      });
    });
  });

  describe("actions", () => {
    it("opens edit pool side panel form", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [factory.resourcePool({ id: 1, permissions: ["edit"] })],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Edit" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Edit" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: EditPool,
        title: "Edit pool",
        props: { id: 1 },
      });
    });

    it("opens delete pool side panel form", async () => {
      mockServer.use(
        poolsResolvers.listPools.handler({
          items: [
            factory.resourcePool({
              id: 1,
              machine_ready_count: 0,
              machine_total_count: 0,
              permissions: ["delete"],
            }),
          ],
          total: 1,
        })
      );

      renderWithProviders(<PoolsTable />);

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: "Delete" })
        ).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: DeletePool,
        title: "Delete pool",
        props: { id: 1 },
      });
    });
  });
});
