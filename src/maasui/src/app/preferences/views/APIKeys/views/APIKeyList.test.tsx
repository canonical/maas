import APIKeyList from "./APIKeyList";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("APIKeyList", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      token: factory.tokenState({
        loading: false,
        loaded: true,
        items: [
          factory.token({
            id: 1,
            key: "ssh-rsa aabb",
            consumer: { key: "abc", name: "Name" },
          }),
        ],
      }),
    });
  });

  it("renders APIKeyAdd", async () => {
    renderWithProviders(<APIKeyList />, { state });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate MAAS API key" })
    );

    expect(
      screen.getByRole("complementary", { name: "Generate MAAS API key" })
    ).toBeInTheDocument();
  });

  it("renders APIKeyEdit", async () => {
    renderWithProviders(<APIKeyList />, { state });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(
      screen.getByRole("complementary", { name: "Edit API key" })
    ).toBeInTheDocument();
  });

  it("renders APIKeyDelete", async () => {
    renderWithProviders(<APIKeyList />, { state });

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      screen.getByRole("complementary", { name: "Delete API key" })
    ).toBeInTheDocument();
  });
});
