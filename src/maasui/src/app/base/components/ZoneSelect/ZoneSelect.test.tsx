import { Formik } from "formik";

import ZoneSelect from "./ZoneSelect";

import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(zoneResolvers.listZones.handler());

describe("ZoneSelect", () => {
  it("renders a list of all zones", async () => {
    renderWithProviders(
      <Formik initialValues={{ zone: "" }} onSubmit={vi.fn()}>
        <ZoneSelect name="zone" />
      </Formik>
    );
    await waitFor(() => {
      expect(zoneResolvers.listZones.resolved).toBeTruthy();
    });

    expect(await screen.findByText("zone-1")).toBeInTheDocument();
    expect(screen.getByText("zone-2")).toBeInTheDocument();
  });

  it("disables select if zones have not loaded", () => {
    renderWithProviders(
      <Formik initialValues={{ zone: "" }} onSubmit={vi.fn()}>
        <ZoneSelect name="zone" />
      </Formik>
    );

    expect(
      screen.getByRole("combobox", { name: new RegExp("zone", "i") })
    ).toBeDisabled();
  });
});
