import * as reduxToolkit from "@reduxjs/toolkit";

import TestMachineForm from "./TestMachineForm";

import { HardwareType } from "@/app/base/enum";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("TestMachineForm", () => {
  let state: RootState;
  const machines = [
    factory.machine({ system_id: "abc123" }),
    factory.machine({ system_id: "def456" }),
  ];

  beforeEach(() => {
    vi.spyOn(query, "generateCallId").mockReturnValue("123456");
    vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("123456");
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: machines,
        statuses: {
          abc123: factory.machineStatus(),
          def456: factory.machineStatus(),
        },
        selected: {
          items: machines.map((machine) => machine.system_id),
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

  it("calls the action to test given machines", async () => {
    // load only the internet connectivity script
    state.script.items = [state.script.items[1]];
    const { store } = renderWithProviders(
      <TestMachineForm isViewingDetails={false} />,
      {
        state,
      }
    );

    await userEvent.click(
      screen.getByRole("checkbox", {
        name: "Allow SSH access and prevent machine powering off",
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
      screen.getByRole("button", { name: "Start tests for 2 machines" })
    );

    expect(
      store.getActions().find((action) => action.type === "machine/test")
    ).toStrictEqual({
      meta: {
        callId: "123456",
        method: "action",
        model: "machine",
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
          filter: {
            id: ["abc123", "def456"],
          },
          system_id: undefined,
        },
      },
      type: "machine/test",
    });
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
      <TestMachineForm
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
});
