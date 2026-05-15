import DeviceOverviewCard from "./DeviceOverviewCard";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DeviceOverviewCard", () => {
  it("shows a spinner for the note if not device details", () => {
    const device = factory.device();
    const state = factory.rootState({
      device: factory.deviceState({ items: [device] }),
    });

    renderWithProviders(<DeviceOverviewCard systemId={device.system_id} />, {
      state,
    });

    expect(screen.getByTestId("loading-note")).toBeInTheDocument();
  });

  it("shows note if device is device details", () => {
    const device = factory.deviceDetails({ description: "description" });
    const state = factory.rootState({
      device: factory.deviceState({ items: [device] }),
    });

    renderWithProviders(<DeviceOverviewCard systemId={device.system_id} />, {
      state,
    });

    expect(screen.queryByTestId("loading-note")).not.toBeInTheDocument();
    expect(screen.getByTestId("device-note")).toHaveTextContent("description");
  });

  it("shows a spinner for the tags if tags have not loaded", () => {
    const device = factory.deviceDetails();
    const state = factory.rootState({
      device: factory.deviceState({ items: [device] }),
      tag: factory.tagState({ loaded: false }),
    });

    renderWithProviders(<DeviceOverviewCard systemId={device.system_id} />, {
      state,
    });

    expect(screen.getByTestId("loading-tags")).toBeInTheDocument();
  });

  it("shows tag names if tags have loaded", () => {
    const device = factory.deviceDetails({ tags: [1, 2] });
    const tags = [
      factory.tag({ id: 1, name: "tag1" }),
      factory.tag({ id: 2, name: "tag2" }),
    ];
    const state = factory.rootState({
      device: factory.deviceState({ items: [device] }),
      tag: factory.tagState({ items: tags, loaded: true }),
    });

    renderWithProviders(<DeviceOverviewCard systemId={device.system_id} />, {
      state,
    });

    expect(screen.queryByTestId("loading-tags")).not.toBeInTheDocument();
    expect(screen.getByTestId("device-tags")).toHaveTextContent("tag1, tag2");
  });
});
