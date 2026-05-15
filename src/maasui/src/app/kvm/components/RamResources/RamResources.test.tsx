import { describe } from "vitest";

import RamResources from "./RamResources";

import { COLOURS } from "@/app/base/constants";
import { renderWithProviders, screen } from "@/testing/utils";

describe("RamResources", () => {
  describe("display", () => {
    describe("displays the columns correctly", () => {
      it("displays the columns correctly", () => {
        renderWithProviders(
          <RamResources
            generalAllocated={1}
            generalFree={2}
            generalOther={3}
            hugepagesAllocated={4}
            hugepagesFree={5}
            hugepagesOther={6}
            pageSize={7}
          />
        );

        ["Allocated", "Others", "Free"].forEach((column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        });
      });

      it("does not show Others if data not provided", () => {
        renderWithProviders(
          <RamResources generalAllocated={1} generalFree={2} />
        );

        expect(
          screen.queryByRole("columnheader", {
            name: new RegExp(`^Others`, "i"),
          })
        ).not.toBeInTheDocument();
      });
    });

    it("can be made to have a dynamic layout", () => {
      renderWithProviders(
        <RamResources dynamicLayout generalAllocated={1} generalFree={2} />
      );

      expect(screen.getByLabelText("ram resources")).toHaveClass(
        "ram-resources--dynamic-layout"
      );
    });

    it("shows General", () => {
      renderWithProviders(
        <RamResources generalAllocated={1} generalFree={2} />
      );

      expect(
        screen.getByRole("row", {
          name: new RegExp(`^General`, "i"),
        })
      ).toBeInTheDocument();
    });

    it("shows Hugepage if data provided", () => {
      renderWithProviders(
        <RamResources
          generalAllocated={1}
          generalFree={2}
          hugepagesAllocated={3}
          hugepagesFree={4}
        />
      );

      expect(
        screen.getByRole("row", {
          name: new RegExp(`^Hugepage`, "i"),
        })
      ).toBeInTheDocument();
    });

    it("hides Hugepage if data not provided", () => {
      renderWithProviders(
        <RamResources generalAllocated={1} generalFree={2} />
      );

      expect(
        screen.queryByRole("row", {
          name: new RegExp(`^Hugepage`, "i"),
        })
      ).not.toBeInTheDocument();
    });

    it("show Hugepage page size if provided", () => {
      renderWithProviders(
        <RamResources
          generalAllocated={1}
          generalFree={2}
          hugepagesAllocated={3}
          hugepagesFree={4}
          pageSize={5}
        />
      );

      expect(screen.getByText("(Size: 5B)")).toBeInTheDocument();
    });

    it("does not show Hugepage page size if not provided", () => {
      renderWithProviders(
        <RamResources
          generalAllocated={1}
          generalFree={2}
          hugepagesAllocated={3}
          hugepagesFree={4}
        />
      );

      expect(
        screen.queryByText(new RegExp(`^\(Size: \d+B\)`, "i"))
      ).not.toBeInTheDocument();
    });

    it("can show whether RAM has been over-committed", () => {
      renderWithProviders(
        <RamResources
          generalAllocated={1}
          generalFree={-1}
          hugepagesAllocated={3}
          hugepagesFree={-1}
        />
      );

      expect(screen.getByTestId("segment")).toHaveStyle(
        `stroke: ${COLOURS.CAUTION}`
      );
    });
  });
});
