import { waitFor } from "@testing-library/react";

import FabricDetailsHeader from "./FabricDetailsHeader";

import { DeleteFabric } from "@/app/networks/views/Fabrics/components";
import type { Fabric } from "@/app/store/fabric/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { user } from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

let state: RootState;
let fabric: Fabric;

const mockServer = setupMockServer(authResolvers.getCurrentUser.handler());
const { mockOpen } = await mockSidePanel();

describe("FabricDetailsHeader", () => {
  beforeEach(() => {
    fabric = factory.fabric({ id: 1, name: "fabric1" });
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [fabric],
      }),
    });
  });

  it("shows the delete button when the user is an admin", async () => {
    renderWithProviders(<FabricDetailsHeader fabric={fabric} />, {
      state,
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Delete fabric" })
      ).toBeInTheDocument();
    });
  });

  it("does not show the delete button if the user is not an admin", () => {
    mockServer.use(
      authResolvers.getCurrentUser.handler(user({ is_superuser: false }))
    );
    renderWithProviders(<FabricDetailsHeader fabric={fabric} />, {
      state,
    });

    expect(screen.queryByRole("button", { name: "Delete fabric" })).toBeNull();
  });

  it("calls a function to open the Delete form when the button is clicked", async () => {
    renderWithProviders(<FabricDetailsHeader fabric={fabric} />, {
      state,
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Delete fabric" })
      ).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Delete fabric" })
    );

    expect(mockOpen).toHaveBeenCalledWith({
      component: DeleteFabric,
      title: "Delete fabric",
      props: { id: fabric.id },
    });
  });
});
