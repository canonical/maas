import DeviceSummary from "./DeviceSummary";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DeviceSummary", () => {
  it("shows a spinner if device has not loaded yet", () => {
    const state = factory.rootState({
      device: factory.deviceState({ items: [] }),
    });

    renderWithProviders(<DeviceSummary systemId="abc123" />, { state });

    expect(screen.getByTestId("loading-device")).toBeInTheDocument();
    expect(screen.queryByTestId("device-summary")).not.toBeInTheDocument();
  });

  it("shows device summary once loaded", () => {
    const state = factory.rootState({
      device: factory.deviceState({
        items: [factory.device({ system_id: "abc123" })],
      }),
    });

    renderWithProviders(<DeviceSummary systemId="abc123" />, { state });

    expect(screen.getByTestId("device-summary")).toBeInTheDocument();
    expect(screen.queryByTestId("loading-device")).not.toBeInTheDocument();
  });
});
