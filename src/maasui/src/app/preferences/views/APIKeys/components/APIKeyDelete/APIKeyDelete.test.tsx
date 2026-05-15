import APIKeyDelete from "./APIKeyDelete";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

const state = factory.rootState({
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

it("renders", () => {
  renderWithProviders(<APIKeyDelete id={1} />, {
    state,
  });
  expect(
    screen.getByRole("form", { name: "Delete API Key" })
  ).toBeInTheDocument();
});
