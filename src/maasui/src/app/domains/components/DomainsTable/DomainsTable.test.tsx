import { describe } from "vitest";

import DomainsTable, { Labels as DomainsTableLabels } from "./DomainsTable";

import SetDefaultForm from "@/app/domains/components/SetDefaultForm";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  mockSidePanel,
  renderWithProviders,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DomainsTable", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      domain: factory.domainState({
        items: [
          factory.domain({
            id: 1,
            name: "b",
            is_default: true,
          }),
          factory.domain({
            id: 2,
            name: "c",
            is_default: false,
          }),
          factory.domain({
            id: 3,
            name: "a",
            is_default: false,
          }),
        ],
      }),
    });
  });

  describe("display", () => {
    it("displays a loading component if domains are loading", async () => {
      state.domain.loading = true;
      renderWithProviders(<DomainsTable />, { state });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      state.domain.items = [];
      renderWithProviders(<DomainsTable />, { state });

      await waitFor(() => {
        expect(screen.getByText("No domains available.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<DomainsTable />, { state });

      ["Domain", "Authoritative", "Hosts", "Total records", "Actions"].forEach(
        (column) => {
          expect(
            screen.getByRole("columnheader", {
              name: new RegExp(`^${column}`, "i"),
            })
          ).toBeInTheDocument();
        }
      );
    });

    it("has a (default) next to the default domain's title", () => {
      renderWithProviders(<DomainsTable />, {
        state,
      });

      expect(
        within(screen.getByRole("row", { name: /^b/ })).getByText("b (default)")
      ).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("triggers the setDefault sidepanel if set default is clicked", async () => {
      renderWithProviders(<DomainsTable />, { state });

      const row = screen.getByRole("row", { name: /^a/ });
      // Only one button is rendered within the contextual menu (the button to open it),
      // which is why I'm doing an unlabelled search - adding an aria-label to the button
      // would require a change to the component in canonical/react-components
      await userEvent.click(
        within(
          within(row).getByLabelText(DomainsTableLabels.Actions)
        ).getByRole("button")
      );

      await userEvent.click(
        screen.getByRole("button", { name: DomainsTableLabels.SetDefault })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          component: SetDefaultForm,
          title: "Set default",
          props: {
            id: state.domain.items[2].id,
          },
        })
      );
    });
  });
});
