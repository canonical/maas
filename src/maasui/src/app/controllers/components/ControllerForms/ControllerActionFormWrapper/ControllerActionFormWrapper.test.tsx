import ControllerActionFormWrapper from "./ControllerActionFormWrapper";

import { controllerActions } from "@/app/store/controller";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("ControllerActionFormWrapper", () => {
  it("can set selected controllers to those that can perform action", async () => {
    const state = factory.rootState();
    const controllers = [
      factory.controller({
        system_id: "abc123",
        actions: [NodeActions.DELETE],
      }),
      factory.controller({ system_id: "def456", actions: [] }),
    ];

    const { store } = renderWithProviders(
      <ControllerActionFormWrapper
        action={NodeActions.DELETE}
        controllers={controllers}
        viewingDetails={false}
      />,
      { initialEntries: ["/controllers"], state }
    );

    await userEvent.click(screen.getByTestId("on-update-selected"));

    const expectedAction = controllerActions.setSelected(["abc123"]);
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
