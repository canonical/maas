import TestControllerForm from "./TestControllerForm";

import { HardwareType } from "@/app/base/enum";
import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("TestControllerForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      controller: factory.controllerState({
        loaded: true,
        items: [
          factory.controller({ system_id: "abc123" }),
          factory.controller({ system_id: "def456" }),
        ],
        statuses: {
          abc123: factory.controllerStatus(),
          def456: factory.controllerStatus(),
        },
      }),
      script: factory.scriptState({
        loaded: true,
        items: [
          factory.script({
            name: "smartctl-validate",
            tags: ["commissioning", "storage"],
            parameters: {
              storage: {
                argument_format: "{path}",
                type: "storage",
              },
            },
            script_type: ScriptType.TESTING,
          }),
          factory.script({
            name: "internet-connectivity",
            tags: ["internet", "network-validation", "network"],
            parameters: {
              url: {
                default: "https://connectivity-check.ubuntu.com",
                description:
                  "A comma seperated list of URLs, IPs, or domains to test if the specified interface has access to. Any protocol supported by curl is support. If no protocol or icmp is given the URL will be pinged.",
                required: true,
              },
            },
            script_type: ScriptType.TESTING,
          }),
        ],
      }),
    });
  });

  it("calls the action to test given controllers", async () => {
    // load only the internet connectivity script
    state.script.items = [state.script.items[1]];
    const { store } = renderWithProviders(
      <TestControllerForm
        controllers={state.controller.items.map(
          (controller) => controller.system_id
        )}
        isViewingDetails={false}
      />,
      { state }
    );

    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Allow SSH access and prevent controller powering off",
      })
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Tests" }),
      "internet-connectivity"
    );
    await userEvent.click(
      screen.getByRole("option", { name: "internet-connectivity" })
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Start tests for 2 controllers" })
    );

    expect(
      store.getActions().filter((action) => action.type === "controller/test")
    ).toStrictEqual([
      {
        meta: {
          method: "action",
          model: "controller",
        },
        payload: {
          params: {
            action: "test",
            extra: {
              enable_ssh: true,
              script_input: {
                "internet-connectivity": {
                  url: "https://connectivity-check.ubuntu.com",
                },
              },
              testing_scripts: ["internet-connectivity"],
            },
            system_id: "abc123",
          },
        },
        type: "controller/test",
      },
      {
        meta: {
          method: "action",
          model: "controller",
        },
        payload: {
          params: {
            action: "test",
            extra: {
              enable_ssh: true,
              script_input: {
                "internet-connectivity": {
                  url: "https://connectivity-check.ubuntu.com",
                },
              },
              testing_scripts: ["internet-connectivity"],
            },
            system_id: "def456",
          },
        },
        type: "controller/test",
      },
    ]);
  });

  it("prepopulates scripts of a given hardwareType", () => {
    const networkScript = factory.script({
      name: "test1",
      hardware_type: HardwareType.Network,
      script_type: ScriptType.TESTING,
    });

    state.script.items = [
      networkScript,
      factory.script({
        name: "test2",
        hardware_type: HardwareType.CPU,
        script_type: ScriptType.TESTING,
      }),
      factory.script({
        name: "test3",
        hardware_type: HardwareType.Memory,
        script_type: ScriptType.TESTING,
      }),
    ];

    renderWithProviders(
      <TestControllerForm
        controllers={state.controller.items.map(
          (controller) => controller.system_id
        )}
        hardwareType={HardwareType.Network}
        isViewingDetails={false}
      />,
      { state }
    );

    expect(screen.getByRole("button", { name: "test1" })).toHaveAttribute(
      "data-testid",
      "selected-tag"
    );
  });

  it("prepopulates scripts with apply_configured_networking", () => {
    const scripts = [
      factory.script({
        name: "test1",
        apply_configured_networking: true,
        script_type: ScriptType.TESTING,
      }),
      factory.script({
        name: "test2",
        apply_configured_networking: false,
        script_type: ScriptType.TESTING,
      }),
      factory.script({
        name: "test3",
        apply_configured_networking: true,
        script_type: ScriptType.TESTING,
      }),
    ];
    state.script.items = scripts;
    renderWithProviders(
      <TestControllerForm
        applyConfiguredNetworking={true}
        controllers={state.controller.items.map(
          (controller) => controller.system_id
        )}
        isViewingDetails={false}
      />,
      { state }
    );

    expect(screen.getByRole("button", { name: "test1" })).toHaveAttribute(
      "data-testid",
      "selected-tag"
    );
  });
});
