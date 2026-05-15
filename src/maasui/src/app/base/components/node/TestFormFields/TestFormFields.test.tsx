import TestMachineForm from "@/app/machines/components/MachineForms/MachineActionFormWrapper/TestMachineForm";
import type { RootState } from "@/app/store/root/types";
import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("TestForm", () => {
  let state: RootState;

  beforeEach(() => {
    const machines = [
      factory.machine({ system_id: "abc123" }),
      factory.machine({ system_id: "def456" }),
    ];
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

  it("displays a field for URL if a selected script has url parameter", async () => {
    renderWithProviders(<TestMachineForm isViewingDetails={false} />, {
      state,
    });
    expect(screen.queryByTestId("url-script-input")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("textbox", { name: "Tests" }));
    await userEvent.click(
      screen.getByRole("option", { name: "internet-connectivity" })
    );
    expect(screen.getByTestId("url-script-input")).toBeInTheDocument();
  });
});
