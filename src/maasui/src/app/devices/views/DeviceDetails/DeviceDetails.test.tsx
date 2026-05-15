import { Route, Routes } from "react-router";

import DeviceDetails from "./DeviceDetails";

import urls from "@/app/base/urls";
import { Label as DeviceConfigurationLabel } from "@/app/devices/components/DeviceConfiguration/DeviceConfiguration";
import { Label as DeviceNetworkLabel } from "@/app/devices/components/DeviceNetwork/DeviceNetwork";
import { Label as DeviceSummaryLabel } from "@/app/devices/components/DeviceSummary/DeviceSummary";
import { deviceActions } from "@/app/store/device";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DeviceDetails", () => {
  const device = factory.deviceDetails({ system_id: "abc123" });
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({
        items: [device],
        loaded: true,
        loading: false,
      }),
    });
  });

  [
    {
      label: DeviceSummaryLabel.Title,
      path: urls.devices.device.summary({ id: "abc123" }),
    },
    {
      label: DeviceNetworkLabel.Title,
      path: urls.devices.device.network({ id: "abc123" }),
    },
    {
      label: DeviceConfigurationLabel.Title,
      path: urls.devices.device.configuration({ id: "abc123" }),
    },
  ].forEach(({ label, path }) => {
    it(`Displays: ${label} at: ${path}`, async () => {
      const { router } = renderWithProviders(
        <Routes>
          <Route
            element={<DeviceDetails />}
            path={`${urls.devices.device.index(null)}/*`}
          />
        </Routes>,
        {
          initialEntries: [urls.devices.device.index({ id: device.system_id })],
          state,
        }
      );
      await router.navigate(path);
      expect(await screen.findByLabelText(label)).toBeInTheDocument();
    });
  });

  it("redirects to summary", () => {
    renderWithProviders(<DeviceDetails />, {
      initialEntries: [urls.devices.device.index({ id: device.system_id })],
      state,
    });
    const { router } = renderWithProviders(
      <Routes>
        <Route
          element={<DeviceDetails />}
          path={`${urls.devices.device.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.devices.device.index({ id: device.system_id })],
        state,
      }
    );
    expect(router.state.location.pathname).toBe(
      urls.devices.device.summary({ id: device.system_id })
    );
  });

  it("gets and sets the device as active", () => {
    const { store } = renderWithProviders(
      <Routes>
        <Route
          element={<DeviceDetails />}
          path={`${urls.devices.device.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.devices.device.index({ id: device.system_id })],
        state,
      }
    );

    const expectedActions = [
      deviceActions.get(device.system_id),
      deviceActions.setActive(device.system_id),
    ];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) => actualAction.type === expectedAction.type
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("unsets active device and cleans up when unmounting", () => {
    const { result, store } = renderWithProviders(
      <Routes>
        <Route
          element={<DeviceDetails />}
          path={`${urls.devices.device.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.devices.device.index({ id: device.system_id })],
        state,
      }
    );

    result.unmount();

    const expectedActions = [
      deviceActions.setActive(null),
      deviceActions.cleanup(),
    ];
    const actualActions = store.getActions();
    expectedActions.forEach((expectedAction) => {
      expect(
        actualActions.find(
          (actualAction) =>
            actualAction.type === expectedAction.type &&
            // Check payload to differentiate "set" and "unset" active actions
            actualAction.payload?.params === expectedAction.payload?.params
        )
      ).toStrictEqual(expectedAction);
    });
  });

  it("displays a message if the device does not exist", () => {
    state.device.items = [];
    renderWithProviders(
      <Routes>
        <Route
          element={<DeviceDetails />}
          path={`${urls.devices.device.index(null)}/*`}
        />
      </Routes>,
      {
        initialEntries: [urls.devices.device.index({ id: device.system_id })],
        state,
      }
    );

    expect(screen.getByTestId("not-found")).toBeInTheDocument();
  });
});
