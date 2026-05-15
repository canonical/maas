import EventLogsTable from "./EventLogsTable";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders, waitFor } from "@/testing/utils";

describe("EventLogsTable", () => {
  describe("display", () => {
    it.skip("displays a loading component if pools are loading", async () => {
      renderWithProviders(<EventLogsTable events={[]} loading={true} />);

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      renderWithProviders(<EventLogsTable events={[]} loading={false} />);

      await waitFor(() => {
        expect(
          screen.getByText("No event logs available.")
        ).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(
        <EventLogsTable
          events={[
            factory.eventRecord({ id: 101, node_id: 1 }),
            factory.eventRecord({ id: 123, node_id: 2 }),
          ]}
          loading={false}
        />
      );

      ["Time", "Event"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });
});
