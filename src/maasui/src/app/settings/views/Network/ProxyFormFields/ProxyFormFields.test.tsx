import ProxyForm from "../ProxyForm";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ProxyFormFields", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        loading: false,
        loaded: true,
        items: [
          {
            name: ConfigNames.HTTP_PROXY,
            value: "http://www.url.com",
          },
          {
            name: ConfigNames.ENABLE_HTTP_PROXY,
            value: false,
          },
          {
            name: ConfigNames.USE_PEER_PROXY,
            value: false,
          },
        ],
      }),
    });
  });

  it("can render", () => {
    renderWithProviders(<ProxyForm />, { state });

    const fields = ["Don't use a proxy", "MAAS built-in", "External", "Peer"];

    fields.forEach((field) => {
      expect(screen.getByRole("radio", { name: field })).toBeInTheDocument();
    });
  });
});
