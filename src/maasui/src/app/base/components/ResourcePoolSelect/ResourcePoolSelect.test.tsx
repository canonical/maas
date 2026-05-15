import { Formik } from "formik";

import ResourcePoolSelect from "./ResourcePoolSelect";

import { mockPools, poolsResolvers } from "@/testing/resolvers/pools";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(poolsResolvers.listPools.handler());

describe("ResourcePoolSelect", () => {
  it("renders a list of all resource pools in state", async () => {
    renderWithProviders(
      <Formik initialValues={{ pool: "" }} onSubmit={vi.fn()}>
        <ResourcePoolSelect name="pool" />
      </Formik>
    );

    await waitFor(() => {
      expect(poolsResolvers.listPools.resolved).toBeTruthy();
    });

    await waitFor(() => {
      expect(
        screen.getByRole("option", { name: "swimming" })
      ).toBeInTheDocument();
    });
    const pools = screen.getAllByRole("option");
    expect(pools).toHaveLength(mockPools.items.length + 1);
  });

  it("disables select if resource pools have not loaded", () => {
    renderWithProviders(
      <Formik initialValues={{ pool: "" }} onSubmit={vi.fn()}>
        <ResourcePoolSelect name="pool" />
      </Formik>
    );

    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
