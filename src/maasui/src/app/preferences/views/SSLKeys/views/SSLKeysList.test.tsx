import { waitFor } from "@testing-library/react";

import SSLKeysList from "@/app/preferences/views/SSLKeys/views/SSLKeysList";
import { sslKeyResolvers } from "@/testing/resolvers/sslKeys";
import {
  renderWithProviders,
  screen,
  userEvent,
  setupMockServer,
} from "@/testing/utils";

setupMockServer(sslKeyResolvers.listSslKeys.handler());

describe("SSLKeysList", () => {
  it("renders AddSSLKey", async () => {
    renderWithProviders(<SSLKeysList />);
    await userEvent.click(screen.getByRole("button", { name: "Add SSL key" }));
    expect(
      screen.getByRole("complementary", { name: "Add SSL key" })
    ).toBeInTheDocument();
  });

  it("renders DeleteSSLKey when valid sslKeyIds are provided", async () => {
    renderWithProviders(<SSLKeysList />);
    await waitFor(() => {
      expect(screen.getAllByRole("button", { name: "Delete" }));
    });
    await userEvent.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    expect(
      screen.getByRole("complementary", { name: "Delete SSL key" })
    ).toBeInTheDocument();
  });

  it("closes side panel form when canceled", async () => {
    renderWithProviders(<SSLKeysList />);
    await userEvent.click(screen.getByRole("button", { name: "Add SSL key" }));
    expect(
      screen.getByRole("complementary", { name: "Add SSL key" })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("complementary", { name: "Add SSL key" })
    ).not.toBeInTheDocument();
  });
});
