import { waitFor } from "@testing-library/react";

import EditPool from "@/app/pools/components/EditPool/EditPool";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  userEvent,
  screen,
  setupMockServer,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  poolsResolvers.getPool.handler(),
  poolsResolvers.updatePool.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditPool", () => {
  const testPoolId = 1;

  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<EditPool id={testPoolId} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("calls update pool on save click", async () => {
    renderWithProviders(<EditPool id={testPoolId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Name (required)")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Name (required)"));

    await userEvent.clear(screen.getByLabelText("Description"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test name 2"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "test description 2"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save pool/i }));

    await waitFor(() => {
      expect(poolsResolvers.updatePool.resolved).toBeTruthy();
    });
  });

  it("displays error message when update pool fails", async () => {
    mockServer.use(
      poolsResolvers.updatePool.error({ code: 400, message: "Uh oh!" }),
      poolsResolvers.updatePool.handler()
    );

    renderWithProviders(<EditPool id={testPoolId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Name (required)")).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save pool/i }));

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });
});
