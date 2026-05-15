import EditZone from "./EditZone";

import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  waitFor,
  setupMockServer,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const mockServer = setupMockServer(
  zoneResolvers.getZone.handler(),
  zoneResolvers.updateZone.handler()
);
const { mockClose } = await mockSidePanel();

describe("EditZone", () => {
  const testZoneId = 1;

  it("runs closeSidePanel function when the cancel button is clicked", async () => {
    renderWithProviders(<EditZone id={testZoneId} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Cancel" })
      ).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("updates a zone on save click", async () => {
    renderWithProviders(<EditZone id={testZoneId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    await userEvent.clear(screen.getByLabelText("Name"));

    await userEvent.clear(screen.getByLabelText("Description"));

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test name 2"
    );

    await userEvent.type(
      screen.getByRole("textbox", { name: /description/i }),
      "test description 2"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save AZ/i }));

    await waitFor(() => {
      expect(zoneResolvers.updateZone.resolved).toBeTruthy();
    });
  });

  it("displays error message when update zone fails", async () => {
    mockServer.use(
      zoneResolvers.updateZone.error({ code: 400, message: "Uh oh!" }),
      zoneResolvers.getZone.handler()
    );

    renderWithProviders(<EditZone id={testZoneId} />);

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toBeInTheDocument();
    });

    await userEvent.type(
      screen.getByRole("textbox", { name: /name/i }),
      "test"
    );

    await userEvent.click(screen.getByRole("button", { name: /Save AZ/i }));

    await waitFor(() => {
      expect(screen.getByText("Uh oh!")).toBeInTheDocument();
    });
  });
});
