import * as reactComponents from "@canonical/react-components";

import ControllerCommissioning from "./ControllerCommissioning";

import { HardwareType } from "@/app/base/enum";
import { scriptResultActions } from "@/app/store/scriptresult";
import { ScriptResultType } from "@/app/store/scriptresult/types";
import { TestStatusStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

vi.mock("@canonical/react-components", async () => {
  const components: typeof reactComponents = await vi.importActual(
    "@canonical/react-components"
  );
  return {
    ...components,
    usePrevious: vi.fn(),
  };
});

it("renders a spinner while script results are loading", () => {
  const state = factory.rootState({
    scriptresult: factory.scriptResultState({
      loading: true,
    }),
  });

  renderWithProviders(<ControllerCommissioning systemId="abc123" />, { state });

  expect(screen.getByLabelText("Loading script results")).toBeInTheDocument();
});

it("fetches script results if they haven't been fetched", () => {
  const controller = factory.controllerDetails();
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    nodescriptresult: factory.nodeScriptResultState({
      items: {
        [controller.system_id]: [],
      },
    }),
    scriptresult: factory.scriptResultState({
      items: [],
      loading: false,
    }),
  });

  const { store } = renderWithProviders(
    <ControllerCommissioning systemId={controller.system_id} />,
    { state }
  );

  const expectedAction = scriptResultActions.getByNodeId(controller.system_id);
  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toStrictEqual(expectedAction);
});

it("fetches script results if the commissioning status changes to pending", () => {
  // Mock the previous commissioning status being different to pending.
  vi.spyOn(reactComponents, "usePrevious").mockImplementation(
    () => TestStatusStatus.PASSED
  );
  const controller = factory.controllerDetails({
    commissioning_status: factory.testStatus({
      status: TestStatusStatus.PENDING, // "new" status is pending
    }),
  });
  const scriptResult = factory.scriptResult({
    hardware_type: HardwareType.Node,
    result_type: ScriptResultType.COMMISSIONING,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    nodescriptresult: factory.nodeScriptResultState({
      items: {
        [controller.system_id]: [scriptResult.id],
      },
    }),
    scriptresult: factory.scriptResultState({
      items: [scriptResult],
    }),
  });

  const { store } = renderWithProviders(
    <ControllerCommissioning systemId={controller.system_id} />,
    { state }
  );

  const expectedAction = scriptResultActions.getByNodeId(controller.system_id);
  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toStrictEqual(expectedAction);
});

it(`does not fetch script results if script results exist and commissioning
    status does not change to pending`, () => {
  const controller = factory.controllerDetails({
    commissioning_status: factory.testStatus({
      status: TestStatusStatus.PASSED,
    }),
  });
  const scriptResult = factory.scriptResult({
    hardware_type: HardwareType.Node,
    result_type: ScriptResultType.COMMISSIONING,
  });
  const state = factory.rootState({
    controller: factory.controllerState({
      items: [controller],
    }),
    nodescriptresult: factory.nodeScriptResultState({
      items: {
        [controller.system_id]: [scriptResult.id],
      },
    }),
    scriptresult: factory.scriptResultState({
      items: [scriptResult],
      loaded: true,
      loading: false,
    }),
  });

  const { store } = renderWithProviders(
    <ControllerCommissioning systemId={controller.system_id} />,
    { state }
  );

  const expectedAction = scriptResultActions.getByNodeId(controller.system_id);
  expect(
    store.getActions().find((action) => action.type === expectedAction.type)
  ).toBeUndefined();
});
