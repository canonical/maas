import selectors from "./selectors";

import { HardwareType } from "@/app/base/enum";
import {
  ScriptResultStatus,
  ScriptResultType,
} from "@/app/store/scriptresult/types";
import * as factory from "@/testing/factories";

describe("scriptResult selectors", () => {
  it("returns all script results", () => {
    const items = [factory.scriptResult(), factory.scriptResult()];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
    });

    expect(selectors.all(state)).toEqual(items);
  });

  it("returns the loading state", () => {
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        loading: true,
      }),
    });

    expect(selectors.loading(state)).toEqual(true);
  });

  it("returns the loaded state", () => {
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        loaded: true,
      }),
    });

    expect(selectors.loaded(state)).toEqual(true);
  });

  it("returns the errors state", () => {
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        errors: "Data is incorrect",
      }),
    });

    expect(selectors.errors(state)).toStrictEqual("Data is incorrect");
  });

  it("returns script results by id", () => {
    const items = [
      factory.scriptResult({ id: 1 }),
      factory.scriptResult({ id: 2 }),
      factory.scriptResult({ id: 3 }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });
    expect(selectors.getById(state, 2)).toStrictEqual(items[1]);
  });

  it("returns script results by node id", () => {
    const resultsForNode = [
      factory.scriptResult({ id: 1 }),
      factory.scriptResult({ id: 2 }),
    ];
    const items = [...resultsForNode, factory.scriptResult({ id: 3 })];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });
    expect(selectors.getByNodeId(state, "abc123")).toStrictEqual(
      resultsForNode
    );
  });

  it("handles no script results for a node", () => {
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items: [
          factory.scriptResult({ id: 1 }),
          factory.scriptResult({ id: 2 }),
          factory.scriptResult({ id: 3 }),
        ],
      }),
      nodescriptresult: factory.nodeScriptResultState(),
    });
    expect(selectors.getByNodeId(state, "abc123")).toStrictEqual(null);
  });

  it("returns hardware testing script results by node id", () => {
    const hardwareResultsForNode = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
    ];
    const items = [
      ...hardwareResultsForNode,
      factory.scriptResult({
        id: 3,
        hardware_type: HardwareType.Storage,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 4,
        result_type: ScriptResultType.COMMISSIONING,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3, 4] },
      }),
    });

    expect(selectors.getHardwareTestingByNodeId(state, "abc123")).toStrictEqual(
      hardwareResultsForNode
    );
  });

  it("returns failed hardware testing script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });
    expect(
      selectors.getHardwareTestingByNodeId(state, "abc123", true)
    ).toStrictEqual([items[0]]);
  });

  it("returns commissioning script results by node id", () => {
    const commissioningResultsForNode = factory.scriptResult({
      id: 1,
      hardware_type: HardwareType.Node,
      result_type: ScriptResultType.COMMISSIONING,
    });

    const items = [
      commissioningResultsForNode,
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.INSTALLATION,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(selectors.getCommissioningByNodeId(state, "abc123")).toStrictEqual([
      commissioningResultsForNode,
    ]);
  });

  it("returns deployment script results by node id", () => {
    const deploymentResultsForNode = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.Node,
        result_type: ScriptResultType.DEPLOYMENT,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.DEPLOYMENT,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.DEPLOYMENT,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items: deploymentResultsForNode,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(selectors.getDeploymentByNodeId(state, "abc123")).toStrictEqual(
      deploymentResultsForNode
    );
  });

  it("returns failed deployment script results by node id", () => {
    const deploymentResultsForNode = factory.scriptResult({
      id: 1,
      hardware_type: HardwareType.Node,
      result_type: ScriptResultType.DEPLOYMENT,
      status: ScriptResultStatus.FAILED,
    });

    const items = [
      deploymentResultsForNode,
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.DEPLOYMENT,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.DEPLOYMENT,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(
      selectors.getDeploymentByNodeId(state, "abc123", true)
    ).toStrictEqual([deploymentResultsForNode]);
  });

  it("returns network testing script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });

    expect(selectors.getNetworkTestingByNodeId(state, "abc123")).toStrictEqual([
      items[1],
    ]);
  });

  it("returns failed network testing script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });
    expect(
      selectors.getNetworkTestingByNodeId(state, "abc123", true)
    ).toStrictEqual([items[0]]);
  });

  it("returns storage testing script results by node id", () => {
    const storageResultsForNode = factory.scriptResult({
      id: 1,
      hardware_type: HardwareType.Storage,
      result_type: ScriptResultType.TESTING,
    });

    const items = [
      storageResultsForNode,
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.COMMISSIONING,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(selectors.getStorageTestingByNodeId(state, "abc123")).toStrictEqual([
      storageResultsForNode,
    ]);
  });

  it("returns failed storage testing script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.Storage,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Storage,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.COMMISSIONING,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });
    expect(
      selectors.getStorageTestingByNodeId(state, "abc123", true)
    ).toStrictEqual([items[0]]);
  });

  it("returns other testing script results by node id", () => {
    const otherResultsForNode = factory.scriptResult({
      id: 1,
      hardware_type: HardwareType.Node,
      result_type: ScriptResultType.TESTING,
    });

    const items = [
      otherResultsForNode,
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.COMMISSIONING,
      }),
    ];

    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(selectors.getOtherTestingByNodeId(state, "abc123")).toStrictEqual([
      otherResultsForNode,
    ]);
  });

  it("returns other failed testing script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.Node,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Node,
        result_type: ScriptResultType.TESTING,
      }),
      factory.scriptResult({
        id: 3,
        result_type: ScriptResultType.COMMISSIONING,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });
    expect(
      selectors.getOtherTestingByNodeId(state, "abc123", true)
    ).toStrictEqual([items[0]]);
  });

  it("returns failed testing script results for node ids", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      // Should not be returned because it passed.
      factory.scriptResult({
        id: 3,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.PASSED,
      }),
      factory.scriptResult({
        id: 4,
        hardware_type: HardwareType.Storage,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.FAILED,
      }),
      // Should not be returned because it is not a testing script.
      factory.scriptResult({
        id: 5,
        result_type: ScriptResultType.COMMISSIONING,
        status: ScriptResultStatus.FAILED,
      }),
      // Should not be returned because it passed.
      factory.scriptResult({
        id: 6,
        result_type: ScriptResultType.TESTING,
        status: ScriptResultStatus.PASSED,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3], def456: [4, 5, 6] },
      }),
    });
    expect(
      selectors.getFailedTestingResultsByNodeIds(state, ["abc123", "def456"])
    ).toStrictEqual({
      abc123: [items[0], items[1]],
      def456: [items[3]],
    });
  });

  it("returns installation script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.INSTALLATION,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.INSTALLATION,
      }),
      factory.scriptResult({
        id: 3,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.TESTING,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(selectors.getInstallationByNodeId(state, "abc123")).toStrictEqual([
      items[0],
      items[1],
    ]);
  });

  it("returns failed installation script results by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.INSTALLATION,
        status: ScriptResultStatus.FAILED,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.INSTALLATION,
      }),
    ];
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2] },
      }),
    });
    expect(
      selectors.getInstallationByNodeId(state, "abc123", true)
    ).toStrictEqual([items[0]]);
  });

  it("returns installation script logs by node id", () => {
    const items = [
      factory.scriptResult({
        id: 1,
        hardware_type: HardwareType.CPU,
        result_type: ScriptResultType.INSTALLATION,
      }),
      factory.scriptResult({
        id: 2,
        hardware_type: HardwareType.Network,
        result_type: ScriptResultType.INSTALLATION,
      }),
    ];
    const logs = {
      1: factory.scriptResultData(),
      2: factory.scriptResultData(),
      3: factory.scriptResultData(),
    };
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        items,
        logs,
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1, 2, 3] },
      }),
    });

    expect(
      selectors.getInstallationLogsByNodeId(state, "abc123")
    ).toStrictEqual([logs["1"], logs["2"]]);
  });

  it("returns a log by id", () => {
    const logs = {
      1: factory.scriptResultData(),
      2: factory.scriptResultData(),
    };
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        logs,
      }),
    });
    expect(selectors.getLogById(state, 2)).toStrictEqual(logs["2"]);
  });

  it("returns history by id", () => {
    const history = {
      1: [factory.partialScriptResult()],
      2: [factory.partialScriptResult()],
    };
    const state = factory.rootState({
      scriptresult: factory.scriptResultState({
        history,
      }),
    });
    expect(selectors.getHistoryById(state, 2)).toStrictEqual(history["2"]);
  });
});
