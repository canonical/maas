import ControllerName from "./ControllerName";

import urls from "@/app/base/urls";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const domain0 = factory.domain();
const domain1 = factory.domain({ id: 99, name: "domain1" });
const controller = factory.controllerDetails({
  domain: domain0,
  locked: false,
  permissions: ["edit"],
  system_id: "abc123",
});

it("can update a controller with the new domain", async () => {
  const state = factory.rootState({
    domain: factory.domainState({
      loaded: true,
      items: [domain0, domain1],
    }),
    general: factory.generalState({
      powerTypes: factory.powerTypesState({
        data: [factory.powerType()],
      }),
    }),
    controller: factory.controllerState({
      loaded: true,
      items: [controller],
    }),
  });

  const { store } = renderWithProviders(
    <ControllerName
      id={controller.system_id}
      isEditing={true}
      setIsEditing={vi.fn()}
    />,
    {
      initialEntries: [
        {
          pathname: urls.controllers.controller.index({
            id: controller.system_id,
          }),
          key: "testKey",
        },
      ],
      state,
    }
  );

  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Domain" }),
    domain1.name
  );

  await userEvent.click(screen.getByRole("button", { name: /Save/ }));

  await waitFor(() => {
    expect(
      store.getActions().find((action) => action.type === "controller/update")
    ).toStrictEqual({
      type: "controller/update",
      payload: {
        params: {
          domain: domain1,
          system_id: controller.system_id,
        },
      },
      meta: {
        model: "controller",
        method: "update",
      },
    });
  });
});
