import { describe } from "vitest";

import VfResources from "./VfResources";

import { renderWithProviders, screen, waitFor } from "@/testing/utils";

describe("VfResources", () => {
  describe("display", () => {
    it("displays a message when rendering an empty list", async () => {
      renderWithProviders(<VfResources interfaces={[]} />);

      await waitFor(() => {
        expect(
          screen.getByText("No interfaces available.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<VfResources interfaces={[]} />);

      ["Interface", "Allocated", "Free"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("can be made to have a dynamic layout", () => {
      renderWithProviders(<VfResources dynamicLayout interfaces={[]} />);

      expect(screen.getByLabelText("VF resources")).toHaveClass(
        "vf-resources--dynamic-layout"
      );
    });

    it("can render as an aggregated meter", () => {
      renderWithProviders(<VfResources interfaces={[]} showAggregated />);

      expect(screen.getByLabelText("vf-resources-meter")).toBeInTheDocument();
      expect(
        screen.queryByLabelText("vf-resources-table")
      ).not.toBeInTheDocument();
    });
  });
});
