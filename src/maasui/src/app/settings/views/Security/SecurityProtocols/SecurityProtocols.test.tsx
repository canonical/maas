import SecurityProtocols from "./SecurityProtocols";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

it("displays loading text if TLS certificate has not loaded", () => {
  const state = factory.rootState({
    general: factory.generalState({
      tlsCertificate: factory.tlsCertificateState({
        data: null,
        loaded: false,
        loading: true,
      }),
    }),
  });
  renderWithProviders(<SecurityProtocols />, { state });

  expect(screen.getByText(/Loading.../)).toBeInTheDocument();
});

it("renders TLS disabled section if no TLS certificate is present", () => {
  const state = factory.rootState({
    general: factory.generalState({
      tlsCertificate: factory.tlsCertificateState({
        data: null,
        loaded: true,
      }),
    }),
  });
  renderWithProviders(<SecurityProtocols />, { state });

  expect(screen.getByText(/TLS disabled/)).toBeInTheDocument();
  expect(screen.queryByText(/TLS enabled/)).not.toBeInTheDocument();
});

it("renders TLS enabled section if TLS certificate is present", () => {
  const state = factory.rootState({
    general: factory.generalState({
      tlsCertificate: factory.tlsCertificateState({
        data: factory.tlsCertificate(),
        loaded: true,
      }),
    }),
  });
  renderWithProviders(<SecurityProtocols />, { state });

  expect(screen.getByText(/TLS enabled/)).toBeInTheDocument();
  expect(screen.queryByText(/TLS disabled/)).not.toBeInTheDocument();
});
