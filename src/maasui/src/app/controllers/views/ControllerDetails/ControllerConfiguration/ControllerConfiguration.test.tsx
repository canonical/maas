import ControllerConfiguration from "./ControllerConfiguration";
import { Label as ConfigurationLabel } from "./ControllerConfigurationForm";
import { Label as PowerConfigurationLabel } from "./ControllerPowerConfiguration";

import { Labels as EditableSectionLabels } from "@/app/base/components/EditableSection";
import { Label as NodeConfigurationFieldsLabel } from "@/app/base/components/NodeConfigurationFields/NodeConfigurationFields";
import { Label as TagFieldLabel } from "@/app/base/components/TagField/TagField";
import { Label as ZoneSelectLabel } from "@/app/base/components/ZoneSelect/ZoneSelect";
import urls from "@/app/base/urls";
import { controllerActions } from "@/app/store/controller";
import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const controller = factory.controllerDetails({ system_id: "abc123" });
const route = urls.controllers.controller.index({ id: controller.system_id });

let state: ReturnType<typeof factory.rootState>;
setupMockServer(
  zoneResolvers.listZones.handler(),
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("ControllerConfiguration", () => {
  beforeEach(() => {
    state = factory.rootState({
      controller: factory.controllerState({
        items: [controller],
        loaded: true,
        loading: false,
      }),
      general: factory.generalState({
        generatedCertificate: factory.generatedCertificateState({
          data: null,
        }),
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              name: PodType.LXD,
              fields: [
                factory.powerField({ name: "power_address" }),
                factory.powerField({ name: "password" }),
              ],
            }),
          ],
          loaded: true,
        }),
      }),
      tag: factory.tagState({
        loaded: true,
        items: [
          factory.tag({ id: 1, name: "tag1" }),
          factory.tag({ id: 2, name: "tag2" }),
        ],
      }),
    });
  });

  it("displays controller configuration sections", async () => {
    renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );

    expect(
      screen.getByRole("heading", { name: /Controller configuration/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Power configuration/i })
    ).toBeInTheDocument();
  });

  it("displays a loading indicator if the controller has not loaded", async () => {
    state.controller.items = [];
    renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );
    expect(
      screen.getByRole("alert", { name: /loading controller configuration/ })
    ).toBeInTheDocument();
  });

  it("displays non-editable controller details by default", async () => {
    renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );

    expect(
      screen.getByTestId("non-editable-controller-details")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("non-editable-controller-power-details")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: ConfigurationLabel.Title })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("form", { name: PowerConfigurationLabel.Title })
    ).not.toBeInTheDocument();
  });

  it("can switch to controller configuration forms", async () => {
    renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );

    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[0]
    );

    expect(
      screen.queryByTestId("non-editable-controller-details")
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("form", { name: ConfigurationLabel.Title })
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[1]
    );
    expect(
      screen.queryByTestId("non-editable-controller-power-details")
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("form", { name: PowerConfigurationLabel.Title })
    ).toBeInTheDocument();
  });

  it("correctly dispatches an action to update a controller", async () => {
    const { store } = renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );
    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[0]
    );
    const note = screen.getByRole("textbox", {
      name: NodeConfigurationFieldsLabel.Note,
    });
    await userEvent.clear(note);
    await userEvent.type(note, "controller's note text");
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: ZoneSelectLabel.Zone }),
      "zone-1"
    );
    await userEvent.click(
      screen.getByRole("textbox", { name: TagFieldLabel.Input })
    );
    await userEvent.click(screen.getByRole("option", { name: "tag1" }));
    await userEvent.click(screen.getByRole("option", { name: "tag2" }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    const expectedAction = controllerActions.update({
      description: "controller's note text",
      tags: [1, 2],
      system_id: controller.system_id,
      zone: { name: "1" },
    });
    const actualActions = store.getActions();

    await waitFor(() => {
      expect(
        actualActions.find((action) => action.type === expectedAction.type)
      ).toStrictEqual(expectedAction);
    });
  });

  it("displays an alert on edit when controller manages more than 1 node", async () => {
    state.controller.items = [{ ...controller, power_bmc_node_count: 3 }];
    renderWithProviders(
      <ControllerConfiguration systemId={controller.system_id} />,
      {
        state,
        initialEntries: [route],
      }
    );
    await userEvent.click(
      screen.getAllByRole("button", {
        name: EditableSectionLabels.EditButton,
      })[2]
    );
    expect(
      screen.getByText(/This power controller manages 2 other nodes/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Changing the IP address or outlet delay will affect all these nodes./
      )
    ).toBeInTheDocument();
  });
});
