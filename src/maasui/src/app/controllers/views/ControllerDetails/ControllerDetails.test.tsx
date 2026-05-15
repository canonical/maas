import { Route, Routes } from "react-router";

import { ControllerDetailsTabLabels } from "../../constants";

import ControllerDetails from "./ControllerDetails";

import urls from "@/app/base/urls";
import { controllerActions } from "@/app/store/controller";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

beforeEach(() => {
  global.scrollTo = vi.fn;
});

afterAll(() => {
  vi.restoreAllMocks();
});

it("gets and sets the controller as active", () => {
  const controller = factory.controller({ system_id: "abc123" });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
      loaded: true,
      loading: false,
    }),
  });

  const { store } = renderWithProviders(<ControllerDetails />, {
    state,
    initialEntries: [
      {
        pathname: urls.controllers.controller.index({
          id: controller.system_id,
        }),
      },
    ],
    pattern: `${urls.controllers.controller.index(null)}/*`,
  });

  const expectedActions = [
    controllerActions.get(controller.system_id),
    controllerActions.setActive(controller.system_id),
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

it("unsets active controller and cleans up when unmounting", () => {
  const controller = factory.controller({ system_id: "abc123" });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
      loaded: true,
      loading: false,
    }),
  });

  const {
    result: { unmount },
    store,
  } = renderWithProviders(<ControllerDetails />, {
    state,
    initialEntries: [
      {
        pathname: urls.controllers.controller.index({
          id: controller.system_id,
        }),
      },
    ],
    pattern: `${urls.controllers.controller.index(null)}/*`,
  });

  unmount();

  const expectedActions = [
    controllerActions.setActive(null),
    controllerActions.cleanup(),
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

it("displays a message if the controller does not exist", () => {
  const controller = factory.controller({ system_id: "abc123" });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
      loaded: true,
      loading: false,
    }),
  });
  renderWithProviders(
    <Routes>
      <Route
        element={<ControllerDetails />}
        path={`${urls.controllers.controller.index(null)}/*`}
      />
    </Routes>,
    {
      state,
      initialEntries: [
        {
          pathname: urls.controllers.controller.index({
            id: "missing-id",
          }),
        },
      ],
    }
  );

  expect(
    screen.getByText(/Unable to find a controller with id/)
  ).toBeInTheDocument();
});

it("gets and sets the controller as active only once when navigating within the same controller", async () => {
  const controller = factory.controller({ system_id: "abc123" });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
      loaded: true,
      loading: false,
    }),
  });

  const { store } = renderWithProviders(<ControllerDetails />, {
    state,
    initialEntries: [
      {
        pathname: urls.controllers.controller.index({
          id: controller.system_id,
        }),
      },
    ],
    pattern: `${urls.controllers.controller.index(null)}/*`,
  });

  await userEvent.click(
    screen.getByRole("link", { name: ControllerDetailsTabLabels.vlans })
  );

  const actualActions = store.getActions();
  const getControllerActions = actualActions.filter(
    (actualAction) =>
      actualAction.type === controllerActions.get(controller.system_id).type
  );
  const setActiveControllerActions = actualActions.filter(
    (actualAction) =>
      actualAction.type ===
      controllerActions.setActive(controller.system_id).type
  );

  expect(getControllerActions).toHaveLength(1);
  expect(setActiveControllerActions).toHaveLength(1);
});
