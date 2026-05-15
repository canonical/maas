import DeviceLink, { Labels } from "./DeviceLink";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

it("handles when devices are loading", () => {
  const state = factory.rootState({
    device: factory.deviceState({ items: [], loading: true }),
  });

  renderWithProviders(<DeviceLink systemId="abc123" />, { state });

  expect(screen.getByLabelText(Labels.LoadingDevices)).toBeInTheDocument();
});

it("handles when a device does not exist", () => {
  const state = factory.rootState({
    device: factory.deviceState({ items: [], loading: false }),
  });

  renderWithProviders(<DeviceLink systemId="abc123" />, {
    state,
  });

  expect(screen.queryByText(/.+/)).not.toBeInTheDocument();
});

it("renders a link if devices have loaded and it exists", () => {
  const device = factory.device();
  const state = factory.rootState({
    device: factory.deviceState({ items: [device], loading: false }),
  });

  renderWithProviders(<DeviceLink systemId={device.system_id} />, { state });

  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    urls.devices.device.index({ id: device.system_id })
  );
});
