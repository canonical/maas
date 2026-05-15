import { Input } from "@canonical/react-components";

import { AddFabric, AddSpace, AddSubnet, AddVlan } from "../../components";

import NetworksHeader from "./NetworksHeader";

import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("NetworksHeader", () => {
  describe("navigation", () => {
    ["Subnets", "VLANs", "Spaces", "Fabrics"].forEach((view) => {
      it(`navigates to the ${view} list when the ${view} tab is clicked`, async () => {
        const { router } = renderWithProviders(<NetworksHeader />);

        await userEvent.click(screen.getByRole("link", { name: view }));

        await waitFor(() => {
          expect(router.state.location.pathname).toBe(
            `/networks/${view.toLowerCase()}`
          );
        });
      });
    });
  });

  describe("display", () => {
    it("renders controls passed in as a prop", () => {
      renderWithProviders(
        <NetworksHeader controls={<Input aria-label="search" type="text" />} />
      );

      expect(
        screen.getByRole("textbox", { name: "search" })
      ).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("displays the form when Add->Fabric is clicked", async () => {
      renderWithProviders(<NetworksHeader />);

      await userEvent.click(screen.getByRole("button", { name: "Add" }));
      await userEvent.click(screen.getByRole("button", { name: "Fabric" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddFabric,
        title: "Add fabric",
      });
    });

    it("displays the form when Add->VLAN is clicked", async () => {
      renderWithProviders(<NetworksHeader />);

      await userEvent.click(screen.getByRole("button", { name: "Add" }));
      await userEvent.click(screen.getByRole("button", { name: "VLAN" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddVlan,
        title: "Add VLAN",
      });
    });

    it("displays the form when Add->Space is clicked", async () => {
      renderWithProviders(<NetworksHeader />);

      await userEvent.click(screen.getByRole("button", { name: "Add" }));
      await userEvent.click(screen.getByRole("button", { name: "Space" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddSpace,
        title: "Add space",
      });
    });

    it("displays the form when Add->Subnet is clicked", async () => {
      renderWithProviders(<NetworksHeader />);

      await userEvent.click(screen.getByRole("button", { name: "Add" }));
      await userEvent.click(screen.getByRole("button", { name: "Subnet" }));

      expect(mockOpen).toHaveBeenCalledWith({
        component: AddSubnet,
        title: "Add subnet",
      });
    });
  });
});
