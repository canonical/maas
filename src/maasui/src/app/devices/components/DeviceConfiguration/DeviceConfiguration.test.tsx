import DeviceConfiguration, { Label } from "./DeviceConfiguration";

import { Labels as EditableSectionLabels } from "@/app/base/components/EditableSection";
import { Label as DeviceConfigurationFieldsLabel } from "@/app/base/components/NodeConfigurationFields/NodeConfigurationFields";
import { Label as TagFieldLabel } from "@/app/base/components/TagField/TagField";
import { Label as ZoneSelectLabel } from "@/app/base/components/ZoneSelect/ZoneSelect";
import { deviceActions } from "@/app/store/device";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  waitFor,
  setupMockServer,
  renderWithProviders,
} from "@/testing/utils";

setupMockServer(zoneResolvers.listZones.handler());

describe("DeviceConfiguration", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      device: factory.deviceState({
        items: [factory.deviceDetails({ system_id: "abc123" })],
        loaded: true,
      }),
      tag: factory.tagState({
        items: [
          factory.tag({ id: 1, name: "tag1" }),
          factory.tag({ id: 2, name: "tag2" }),
        ],
      }),
    });
  });

  it("displays a spinner if the device has not loaded yet", async () => {
    state.device.items = [];
    renderWithProviders(<DeviceConfiguration systemId="abc123" />, {
      state,
    });
    await waitFor(() => {
      expect(screen.getByTestId("loading-device")).toBeInTheDocument();
    });
    expect(screen.getByTestId("loading-device")).toBeInTheDocument();
  });

  it("shows the device details by default", async () => {
    renderWithProviders(<DeviceConfiguration systemId="abc123" />, {
      state,
    });
    await waitFor(() => {
      expect(screen.getByTestId("device-details")).toBeInTheDocument();
    });
    expect(screen.getByTestId("device-details")).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: Label.Form })
    ).not.toBeInTheDocument();
  });

  it("can switch to showing the device configuration form", async () => {
    renderWithProviders(<DeviceConfiguration systemId="abc123" />, {
      state,
    });
    await waitFor(() => {
      expect(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[0]
    );

    expect(screen.queryByTestId("device-details")).not.toBeInTheDocument();
    expect(screen.getByRole("form", { name: Label.Form })).toBeInTheDocument();
  });

  it("correctly dispatches an action to update a device", async () => {
    const { store } = renderWithProviders(
      <DeviceConfiguration systemId="abc123" />,
      {
        state,
      }
    );
    await waitFor(() => {
      expect(
        screen.getAllByRole("button", {
          name: EditableSectionLabels.EditButton,
        })[0]
      ).toBeInTheDocument();
    });
    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[0]
    );
    const deviceNote = screen.getByRole("textbox", {
      name: DeviceConfigurationFieldsLabel.Note,
    });
    await userEvent.clear(deviceNote);
    await userEvent.type(deviceNote, "it's a device");
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: ZoneSelectLabel.Zone }),
      "zone-1"
    );
    // Open the tag selector dropdown.
    await userEvent.click(
      screen.getByRole("textbox", { name: TagFieldLabel.Input })
    );
    await userEvent.click(screen.getByRole("option", { name: "tag1" }));
    await userEvent.click(screen.getByRole("option", { name: "tag2" }));
    await userEvent.click(screen.getByRole("button", { name: Label.Submit }));
    const expectedAction = deviceActions.update({
      description: "it's a device",
      tags: [1, 2],
      system_id: "abc123",
      zone: { name: "1" },
    });
    const actualActions = store.getActions();
    await waitFor(() => {
      expect(
        actualActions.find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });
});
