import APIKeyList, { Label as APIKeyListLabels } from "./APIKeyTable";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("APIKeyList", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      token: factory.tokenState({
        items: [
          factory.token({
            id: 1,
            key: "ssh-rsa aabb",
            consumer: { key: "abc", name: "Name" },
          }),
          factory.token({
            id: 2,
            key: "ssh-rsa ccdd",
            consumer: { key: "abc", name: "Name" },
          }),
        ],
      }),
    });
  });

  it("can render the table", () => {
    renderWithProviders(<APIKeyList />, { state });
    expect(
      screen.getByRole("grid", { name: APIKeyListLabels.Title })
    ).toBeInTheDocument();
  });

  it("can display an empty state message", () => {
    state.token.items = [];
    renderWithProviders(<APIKeyList />, {
      state,
    });

    expect(screen.getByText(APIKeyListLabels.EmptyList)).toBeInTheDocument();
  });
});
