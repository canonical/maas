import SelectUpstreamImagesForm from "./SelectUpstreamImagesForm";

import { imageResolvers } from "@/testing/resolvers/images";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(
  imageResolvers.listSelections.handler(),
  imageResolvers.listAvailableSelections.handler(),
  imageResolvers.addSelections.handler()
);

describe("SelectUpstreamImagesForm", () => {
  it("correctly filters selection options", async () => {
    renderWithProviders(<SelectUpstreamImagesForm />);
    await waitFor(() => {
      expect(
        screen.getByRole("row", {
          name: "24.04 LTS noble",
          hidden: true,
        })
      ).toBeInTheDocument();
    });

    const rowAvailable = within(
      screen.getByRole("row", {
        name: "24.04 LTS noble",
        hidden: true,
      })
    ).getAllByRole("combobox", { hidden: true });
    expect(rowAvailable).toHaveLength(1);
    await userEvent.click(rowAvailable[0]);
    expect(screen.getByText("arm64")).toBeInTheDocument();
    expect(screen.queryByText("amd64")).not.toBeInTheDocument();
  });

  it("can dispatch an action to save ubuntu images", async () => {
    renderWithProviders(<SelectUpstreamImagesForm />);
    await waitFor(() => {
      expect(
        screen.getByRole("row", {
          name: "24.04 LTS noble",
          hidden: true,
        })
      ).toBeInTheDocument();
    });

    const rowAvailable = within(
      screen.getByRole("row", {
        name: "24.04 LTS noble",
        hidden: true,
      })
    ).getAllByRole("combobox", { hidden: true });

    await userEvent.click(rowAvailable[0]);
    expect(screen.getByText("arm64")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "arm64" }));

    await userEvent.click(
      screen.getByRole("button", { name: "Save and sync" })
    );
    await waitFor(() => {
      expect(imageResolvers.addSelections.resolved).toBeTruthy();
    });
  });
});
