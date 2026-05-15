import { actions } from "./slice";
import { FetchSortDirection, FilterGroupKey } from "./types";
import { FetchGroupKey } from "./types/actions";

import { PowerTypeNames } from "@/app/store/general/constants";
import {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import { ScriptName } from "@/app/store/script/types";
import {
  BridgeType,
  DiskTypes,
  NetworkLinkMode,
  StorageLayout,
} from "@/app/store/types/enum";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("machine actions", () => {
  it("should handle fetching machines", () => {
    expect(actions.fetch("123456")).toEqual({
      type: "machine/fetch",
      meta: {
        model: "machine",
        method: "list",
        nocache: true,
        callId: "123456",
      },
      payload: null,
    });
  });

  it("should handle fetching machines with params", () => {
    const params = {
      filter: {
        owner: "admin",
      },
      group_key: FetchGroupKey.Owner,
      group_collapsed: [],
      page_size: 20,
      page_number: 5,
      sort_key: FetchGroupKey.Owner,
      sort_direction: FetchSortDirection.Ascending,
    };
    expect(actions.fetch("123456", params)).toEqual({
      type: "machine/fetch",
      meta: {
        model: "machine",
        method: "list",
        nocache: true,
        callId: "123456",
      },
      payload: {
        params,
      },
    });
  });

  it("can get machines", () => {
    expect(actions.get("abc123", "123456")).toEqual({
      type: "machine/get",
      meta: {
        model: "machine",
        method: "get",
        callId: "123456",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can get a count of machines", () => {
    expect(actions.count("123456")).toEqual({
      type: "machine/count",
      meta: {
        model: "machine",
        method: "count",
        callId: "123456",
      },
      payload: null,
    });
  });

  it("can get a count of filtered machines", () => {
    expect(actions.count("123456", { owner: "admin" })).toEqual({
      type: "machine/count",
      meta: {
        model: "machine",
        method: "count",
        callId: "123456",
      },
      payload: { params: { filter: { owner: "admin" } } },
    });
  });

  it("can set an active machine", () => {
    expect(actions.setActive("abc123")).toEqual({
      type: "machine/setActive",
      meta: {
        model: "machine",
        method: "set_active",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can set selected machines", () => {
    expect(actions.setSelected({ items: ["abc123", "def456"] })).toEqual({
      type: "machine/setSelected",
      payload: { items: ["abc123", "def456"] },
    });
  });

  it("can handle creating machines", () => {
    expect(
      actions.create({
        hostname: "machine1",
        description: "a machine",
        extra_macs: [],
        power_parameters: {},
        power_type: PowerTypeNames.MANUAL,
        pxe_mac: "",
      })
    ).toEqual({
      type: "machine/create",
      meta: {
        model: "machine",
        method: "create",
      },
      payload: {
        params: {
          hostname: "machine1",
          description: "a machine",
          extra_macs: [],
          power_parameters: {},
          power_type: PowerTypeNames.MANUAL,
          pxe_mac: "",
        },
      },
    });
  });

  it("can handle updating machines", () => {
    expect(
      actions.update({
        system_id: "abc123",
        hostname: "machine1",
        description: "a machine",
        extra_macs: [],
        pxe_mac: "",
      })
    ).toEqual({
      type: "machine/update",
      meta: {
        model: "machine",
        method: "update",
      },
      payload: {
        params: {
          system_id: "abc123",
          hostname: "machine1",
          description: "a machine",
          extra_macs: [],
          pxe_mac: "",
        },
      },
    });
  });

  it("can handle setting the pool", () => {
    expect(
      actions.setPool({
        system_id: "abc123",
        pool_id: 909,
      })
    ).toEqual({
      type: "machine/setPool",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_POOL,
          extra: {
            pool_id: 909,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle setting the pool for a selection of machines", () => {
    expect(
      actions.setPool({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        pool_id: 909,
      })
    ).toEqual({
      type: "machine/setPool",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_POOL,
          extra: {
            pool_id: 909,
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle setting the zone", () => {
    expect(actions.setZone({ system_id: "abc123", zone_id: 909 })).toEqual({
      type: "machine/setZone",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_ZONE,
          extra: {
            zone_id: 909,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle setting the zone for a selection of machines", () => {
    expect(
      actions.setZone({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        zone_id: 909,
      })
    ).toEqual({
      type: "machine/setZone",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.SET_ZONE,
          extra: {
            zone_id: 909,
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle turning on the machine", () => {
    expect(actions.on({ system_id: "abc123" })).toEqual({
      type: "machine/on",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ON,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle turning on a selection of machines", () => {
    expect(
      actions.on({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/on",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ON,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle turning off the machine", () => {
    expect(actions.off({ system_id: "abc123" })).toEqual({
      type: "machine/off",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.OFF,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle turning off a selection of machines", () => {
    expect(
      actions.off({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/off",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.OFF,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle checking the machine power", () => {
    expect(actions.checkPower("abc123")).toEqual({
      type: "machine/checkPower",
      meta: {
        model: "machine",
        method: "check_power",
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle acquiring a machine", () => {
    expect(actions.acquire({ system_id: "abc123" })).toEqual({
      type: "machine/acquire",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ACQUIRE,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle acquiring a selection of machines", () => {
    expect(
      actions.acquire({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/acquire",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ACQUIRE,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle releasing a machine", () => {
    expect(
      actions.release({
        erase: true,
        quick_erase: false,
        secure_erase: true,
        system_id: "abc123",
      })
    ).toEqual({
      type: "machine/release",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.RELEASE,
          extra: { erase: true, quick_erase: false, secure_erase: true },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle releasing a selection of machines", () => {
    expect(
      actions.release({
        erase: true,
        quick_erase: false,
        secure_erase: true,
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/release",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.RELEASE,
          extra: { erase: true, quick_erase: false, secure_erase: true },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle deploying a machine", () => {
    expect(
      actions.deploy({
        distro_series: "bionic",
        ephemeral_deploy: false,
        hwe_kernel: "ga-16.04",
        install_kvm: false,
        osystem: "ubuntu",
        system_id: "abc123",
        enable_kernel_crash_dump: false,
      })
    ).toEqual({
      type: "machine/deploy",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.DEPLOY,
          extra: {
            distro_series: "bionic",
            ephemeral_deploy: false,
            hwe_kernel: "ga-16.04",
            install_kvm: false,
            osystem: "ubuntu",
            enable_kernel_crash_dump: false,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deploying a selection of machines", () => {
    expect(
      actions.deploy({
        distro_series: "bionic",
        ephemeral_deploy: false,
        hwe_kernel: "ga-16.04",
        install_kvm: false,
        osystem: "ubuntu",
        enable_kernel_crash_dump: false,
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/deploy",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.DEPLOY,
          extra: {
            distro_series: "bionic",
            ephemeral_deploy: false,
            hwe_kernel: "ga-16.04",
            install_kvm: false,
            osystem: "ubuntu",
            enable_kernel_crash_dump: false,
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle getting a summary XML file", () => {
    expect(
      actions.getSummaryXml({ systemId: "abc123", fileId: "file1" })
    ).toEqual({
      type: "machine/getSummaryXml",
      meta: {
        fileContextKey: "file1",
        model: "machine",
        method: "get_summary_xml",
        useFileContext: true,
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle getting a summary YAML file", () => {
    expect(
      actions.getSummaryYaml({ systemId: "abc123", fileId: "file1" })
    ).toEqual({
      type: "machine/getSummaryYaml",
      meta: {
        fileContextKey: "file1",
        model: "machine",
        method: "get_summary_yaml",
        useFileContext: true,
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle aborting a machine", () => {
    expect(actions.abort({ system_id: "abc123" })).toEqual({
      type: "machine/abort",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ABORT,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle aborting a selection of machines", () => {
    expect(
      actions.abort({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/abort",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.ABORT,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle commissioning a machine", () => {
    expect(
      actions.commission({
        commissioning_scripts: [
          ScriptName.UPDATE_FIRMWARE,
          ScriptName.CONFIGURE_HBA,
        ],
        enable_ssh: true,
        script_input: { testingScript0: { url: "www.url.com" } },
        skip_bmc_config: false,
        skip_networking: false,
        skip_storage: false,
        system_id: "abc123",
        testing_scripts: ["test0", "test2"],
      })
    ).toEqual({
      meta: {
        method: "action",
        model: "machine",
      },
      payload: {
        params: {
          action: NodeActions.COMMISSION,
          extra: {
            commissioning_scripts: [
              ScriptName.UPDATE_FIRMWARE,
              ScriptName.CONFIGURE_HBA,
            ],
            enable_ssh: true,
            script_input: { testingScript0: { url: "www.url.com" } },
            skip_bmc_config: false,
            skip_networking: false,
            skip_storage: false,
            testing_scripts: ["test0", "test2"],
          },
          system_id: "abc123",
        },
      },
      type: "machine/commission",
    });
  });

  it("can handle commissioning a selection of machines", () => {
    expect(
      actions.commission({
        commissioning_scripts: [
          ScriptName.UPDATE_FIRMWARE,
          ScriptName.CONFIGURE_HBA,
        ],
        enable_ssh: true,
        script_input: { testingScript0: { url: "www.url.com" } },
        skip_bmc_config: false,
        skip_networking: false,
        skip_storage: false,
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        testing_scripts: ["test0", "test2"],
      })
    ).toEqual({
      meta: {
        method: "action",
        model: "machine",
      },
      payload: {
        params: {
          action: NodeActions.COMMISSION,
          extra: {
            commissioning_scripts: [
              ScriptName.UPDATE_FIRMWARE,
              ScriptName.CONFIGURE_HBA,
            ],
            enable_ssh: true,
            script_input: { testingScript0: { url: "www.url.com" } },
            skip_bmc_config: false,
            skip_networking: false,
            skip_storage: false,
            testing_scripts: ["test0", "test2"],
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
      type: "machine/commission",
    });
  });

  it("can handle testing a machine", () => {
    expect(
      actions.test({
        enable_ssh: true,
        script_input: { "test-0": { url: "www.url.com" } },
        system_id: "abc123",
        testing_scripts: ["test1", "test2"],
      })
    ).toEqual({
      type: "machine/test",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.TEST,
          extra: {
            enable_ssh: true,
            script_input: { "test-0": { url: "www.url.com" } },
            testing_scripts: ["test1", "test2"],
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle testing for a selection of machines", () => {
    expect(
      actions.test({
        enable_ssh: true,
        script_input: { "test-0": { url: "www.url.com" } },
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        testing_scripts: ["test1", "test2"],
      })
    ).toEqual({
      type: "machine/test",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.TEST,
          extra: {
            enable_ssh: true,
            script_input: { "test-0": { url: "www.url.com" } },
            testing_scripts: ["test1", "test2"],
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can create a suppress script results action", () => {
    expect(
      actions.suppressScriptResults("abc123", [
        factory.scriptResult({ id: 0, name: "script0" }),
        factory.scriptResult({ id: 2, name: "script2" }),
      ])
    ).toEqual({
      meta: {
        method: "set_script_result_suppressed",
        model: "machine",
      },
      payload: {
        params: {
          script_result_ids: [0, 2],
          system_id: "abc123",
        },
      },
      type: "machine/suppressScriptResults",
    });
  });

  it("can putting a machine into rescue mode", () => {
    expect(actions.rescueMode({ system_id: "abc123" })).toEqual({
      type: "machine/rescueMode",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.RESCUE_MODE,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can putting a selection of machines into rescue mode", () => {
    expect(
      actions.rescueMode({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/rescueMode",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.RESCUE_MODE,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle making a machine exit rescue mode", () => {
    expect(actions.exitRescueMode({ system_id: "abc123" })).toEqual({
      type: "machine/exitRescueMode",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.EXIT_RESCUE_MODE,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle making a selection of machines exit rescue mode", () => {
    expect(
      actions.exitRescueMode({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/exitRescueMode",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.EXIT_RESCUE_MODE,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle marking a machine as broken", () => {
    expect(
      actions.markBroken({ system_id: "abc123", message: "machine is on fire" })
    ).toEqual({
      type: "machine/markBroken",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.MARK_BROKEN,
          extra: {
            message: "machine is on fire",
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle marking a selection of machines as broken", () => {
    expect(
      actions.markBroken({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        message: "machine is on fire",
      })
    ).toEqual({
      type: "machine/markBroken",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.MARK_BROKEN,
          extra: {
            message: "machine is on fire",
          },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle marking a machine as fixed", () => {
    expect(actions.markFixed({ system_id: "abc123" })).toEqual({
      type: "machine/markFixed",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.MARK_FIXED,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle marking a selection of machines as fixed", () => {
    expect(
      actions.markFixed({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/markFixed",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.MARK_FIXED,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle overriding failed testing on a machine", () => {
    expect(actions.overrideFailedTesting({ system_id: "abc123" })).toEqual({
      type: "machine/overrideFailedTesting",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.OVERRIDE_FAILED_TESTING,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle suppressing script results for a selection of machines", () => {
    expect(
      actions.overrideFailedTesting({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        suppress_failed_script_results: true,
      })
    ).toEqual({
      type: "machine/overrideFailedTesting",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.OVERRIDE_FAILED_TESTING,
          extra: { suppress_failed_script_results: true },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle overriding failed testing for a selection of machines", () => {
    expect(
      actions.overrideFailedTesting({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/overrideFailedTesting",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.OVERRIDE_FAILED_TESTING,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle locking a machine", () => {
    expect(actions.lock({ system_id: "abc123" })).toEqual({
      type: "machine/lock",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.LOCK,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle locking a selection of machines", () => {
    expect(
      actions.lock({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/lock",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.LOCK,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle unlocking a machine", () => {
    expect(actions.unlock({ system_id: "abc123" })).toEqual({
      type: "machine/unlock",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.UNLOCK,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle unlocking a selection of machines", () => {
    expect(
      actions.unlock({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/unlock",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.UNLOCK,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle deleting a machine", () => {
    expect(actions.delete({ system_id: "abc123" })).toEqual({
      type: "machine/delete",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.DELETE,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a selection of machines", () => {
    expect(
      actions.delete({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
      })
    ).toEqual({
      type: "machine/delete",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.DELETE,
          extra: {},
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle tagging a machine", () => {
    expect(actions.tag({ system_id: "abc123", tags: [1, 2] })).toEqual({
      type: "machine/tag",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.TAG,
          extra: { tags: [1, 2] },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle tagging a selection of machines", () => {
    expect(
      actions.tag({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        tags: [1, 2],
      })
    ).toEqual({
      type: "machine/tag",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.TAG,
          extra: { tags: [1, 2] },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle untagging a machine", () => {
    expect(actions.untag({ system_id: "abc123", tags: [1, 2] })).toEqual({
      type: "machine/untag",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.UNTAG,
          extra: { tags: [1, 2] },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle untagging a selection of machines", () => {
    expect(
      actions.untag({
        filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        tags: [1, 2],
      })
    ).toEqual({
      type: "machine/untag",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.UNTAG,
          extra: { tags: [1, 2] },
          filter: { hostname: ["ringtail-possum", "easter-rosella"] },
        },
      },
    });
  });

  it("can handle cloning a machine", () => {
    expect(
      actions.clone({
        filter: { id: ["def456", "ghi789"] },
        interfaces: true,
        storage: false,
        system_id: "abc123",
      })
    ).toEqual({
      type: "machine/clone",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.CLONE,
          filter: { id: ["def456", "ghi789"] },
          extra: {
            interfaces: true,
            storage: false,
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle cloning a selection of machines", () => {
    expect(
      actions.clone({
        system_id: "abc123",
        interfaces: true,
        storage: false,
        filter: { id: ["def456", "ghi789"] },
      })
    ).toEqual({
      type: "machine/clone",
      meta: {
        model: "machine",
        method: "action",
      },
      payload: {
        params: {
          system_id: "abc123",
          action: NodeActions.CLONE,
          extra: {
            interfaces: true,
            storage: false,
          },
          filter: { id: ["def456", "ghi789"] },
        },
      },
    });
  });

  it("can handle applying a machine's storage layout", () => {
    expect(
      actions.applyStorageLayout({
        systemId: "abc123",
        storageLayout: StorageLayout.BLANK,
      })
    ).toEqual({
      type: "machine/applyStorageLayout",
      meta: {
        model: "machine",
        method: "apply_storage_layout",
      },
      payload: {
        params: {
          storage_layout: StorageLayout.BLANK,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a bcache with all params", () => {
    expect(
      actions.createBcache({
        blockId: 1,
        cacheMode: "WRITEBACK",
        cacheSetId: 2,
        fstype: "fat32",
        mountOptions: "size=1024k",
        mountPoint: "/path",
        name: "bcache1",
        partitionId: 3,
        systemId: "abc123",
        tags: ["tag1", "tag2"],
      })
    ).toEqual({
      type: "machine/createBcache",
      meta: {
        model: "machine",
        method: "create_bcache",
      },
      payload: {
        params: {
          block_id: 1,
          cache_mode: "WRITEBACK",
          cache_set: 2,
          fstype: "fat32",
          mount_options: "size=1024k",
          mount_point: "/path",
          name: "bcache1",
          partition_id: 3,
          system_id: "abc123",
          tags: ["tag1", "tag2"],
        },
      },
    });
  });

  it("can handle creating a bcache with only required params", () => {
    expect(
      actions.createBcache({
        cacheMode: "WRITEBACK",
        cacheSetId: 2,
        name: "bcache1",
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createBcache",
      meta: {
        model: "machine",
        method: "create_bcache",
      },
      payload: {
        params: {
          cache_mode: "WRITEBACK",
          cache_set: 2,
          name: "bcache1",
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a bond", () => {
    expect(
      actions.createBond({
        bond_downdelay: 1,
        bond_lacp_rate: BondLacpRate.SLOW,
        bond_miimon: 3,
        bond_mode: BondMode.ACTIVE_BACKUP,
        bond_num_grat_arp: 4,
        bond_updelay: 5,
        bond_xmit_hash_policy: BondXmitHashPolicy.ENCAP2_3,
        interface_speed: 6,
        link_connected: true,
        link_speed: 7,
        mac_address: "2a:67:d7:a7:0f:f9",
        mode: NetworkLinkMode.AUTO,
        name: "eth0",
        parents: [1, 2],
        system_id: "abc123",
        tags: ["koala", "tag"],
        vlan: 9,
      })
    ).toEqual({
      type: "machine/createBond",
      meta: {
        model: "machine",
        method: "create_bond",
      },
      payload: {
        params: {
          bond_downdelay: 1,
          bond_lacp_rate: BondLacpRate.SLOW,
          bond_miimon: 3,
          bond_mode: BondMode.ACTIVE_BACKUP,
          bond_num_grat_arp: 4,
          bond_updelay: 5,
          bond_xmit_hash_policy: BondXmitHashPolicy.ENCAP2_3,
          interface_speed: 6,
          link_connected: true,
          link_speed: 7,
          mac_address: "2a:67:d7:a7:0f:f9",
          mode: NetworkLinkMode.AUTO,
          name: "eth0",
          parents: [1, 2],
          system_id: "abc123",
          tags: ["koala", "tag"],
          vlan: 9,
        },
      },
    });
  });

  it("can handle creating a bridge", () => {
    expect(
      actions.createBridge({
        bridge_fd: 2,
        bridge_stp: true,
        bridge_type: BridgeType.STANDARD,
        interface_speed: 5,
        link_connected: true,
        link_speed: 10,
        mac_address: "2a:67:d7:a7:0f:f9",
        mode: NetworkLinkMode.AUTO,
        name: "eth0",
        parents: [1],
        system_id: "abc123",
        tags: ["koala", "tag"],
        vlan: 9,
      })
    ).toEqual({
      type: "machine/createBridge",
      meta: {
        model: "machine",
        method: "create_bridge",
      },
      payload: {
        params: {
          bridge_fd: 2,
          bridge_stp: true,
          bridge_type: BridgeType.STANDARD,
          interface_speed: 5,
          link_connected: true,
          link_speed: 10,
          mac_address: "2a:67:d7:a7:0f:f9",
          mode: NetworkLinkMode.AUTO,
          name: "eth0",
          parents: [1],
          system_id: "abc123",
          tags: ["koala", "tag"],
          vlan: 9,
        },
      },
    });
  });

  it("can handle creating a cache set with all params", () => {
    expect(
      actions.createCacheSet({
        blockId: 1,
        partitionId: 2,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createCacheSet",
      meta: {
        model: "machine",
        method: "create_cache_set",
      },
      payload: {
        params: {
          block_id: 1,
          partition_id: 2,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a cache set with only required params", () => {
    expect(
      actions.createCacheSet({
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createCacheSet",
      meta: {
        model: "machine",
        method: "create_cache_set",
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a logical volume with all values", () => {
    expect(
      actions.createLogicalVolume({
        fstype: "fat32",
        mountOptions: "noexec",
        mountPoint: "/path",
        name: "logical-volume",
        size: 1000,
        systemId: "abc123",
        tags: ["tag1", "tag2"],
        volumeGroupId: 1,
      })
    ).toEqual({
      type: "machine/createLogicalVolume",
      meta: {
        model: "machine",
        method: "create_logical_volume",
      },
      payload: {
        params: {
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          name: "logical-volume",
          size: 1000,
          system_id: "abc123",
          tags: ["tag1", "tag2"],
          volume_group_id: 1,
        },
      },
    });
  });

  it("can handle creating a logical volume with only required values", () => {
    expect(
      actions.createLogicalVolume({
        name: "logical-volume",
        size: 1000,
        systemId: "abc123",
        volumeGroupId: 1,
      })
    ).toEqual({
      type: "machine/createLogicalVolume",
      meta: {
        model: "machine",
        method: "create_logical_volume",
      },
      payload: {
        params: {
          name: "logical-volume",
          size: 1000,
          system_id: "abc123",
          volume_group_id: 1,
        },
      },
    });
  });

  it("can handle creating a partition", () => {
    expect(
      actions.createPartition({
        blockId: 1,
        fstype: "fat32",
        mountOptions: "noexec",
        mountPoint: "/path",
        partitionSize: 1000,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createPartition",
      meta: {
        model: "machine",
        method: "create_partition",
      },
      payload: {
        params: {
          block_id: 1,
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          partition_size: 1000,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a physical interface", () => {
    expect(
      actions.createPhysical({
        enabled: true,
        interface_speed: 10,
        ip_address: "1.2.3.4",
        ip_assignment: "external",
        link_connected: true,
        link_speed: 10,
        mac_address: "2a:67:d7:a7:0f:f9",
        mode: NetworkLinkMode.AUTO,
        name: "eth0",
        numa_node: 1,
        system_id: "abc123",
        tags: ["koala", "tag"],
        vlan: 9,
      })
    ).toEqual({
      type: "machine/createPhysical",
      meta: {
        model: "machine",
        method: "create_physical",
      },
      payload: {
        params: {
          enabled: true,
          interface_speed: 10,
          ip_address: "1.2.3.4",
          ip_assignment: "external",
          link_connected: true,
          link_speed: 10,
          mac_address: "2a:67:d7:a7:0f:f9",
          mode: NetworkLinkMode.AUTO,
          name: "eth0",
          numa_node: 1,
          system_id: "abc123",
          tags: ["koala", "tag"],
          vlan: 9,
        },
      },
    });
  });

  it("can handle creating a physical interface with only required params", () => {
    expect(
      actions.createPhysical({
        mac_address: "2a:67:d7:a7:0f:f9",
        mode: NetworkLinkMode.AUTO,
        system_id: "abc123",
      })
    ).toEqual({
      type: "machine/createPhysical",
      meta: {
        model: "machine",
        method: "create_physical",
      },
      payload: {
        params: {
          mac_address: "2a:67:d7:a7:0f:f9",
          mode: NetworkLinkMode.AUTO,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a RAID with all values", () => {
    expect(
      actions.createRaid({
        blockDeviceIds: [1, 2],
        fstype: "tmpfs",
        level: DiskTypes.RAID_0,
        mountOptions: "noexec",
        mountPoint: "/path",
        name: "raid1",
        partitionIds: [4, 5],
        spareBlockDeviceIds: [6, 7],
        sparePartitionIds: [8, 9],
        systemId: "abc123",
        tags: ["tag1", "tag2"],
      })
    ).toEqual({
      type: "machine/createRaid",
      meta: {
        model: "machine",
        method: "create_raid",
      },
      payload: {
        params: {
          block_devices: [1, 2],
          fstype: "tmpfs",
          level: "raid-0",
          mount_options: "noexec",
          mount_point: "/path",
          name: "raid1",
          partitions: [4, 5],
          spare_devices: [6, 7],
          spare_partitions: [8, 9],
          system_id: "abc123",
          tags: ["tag1", "tag2"],
        },
      },
    });
  });

  it("can handle creating a RAID with only required values", () => {
    expect(
      actions.createRaid({
        level: DiskTypes.RAID_0,
        name: "raid1",
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createRaid",
      meta: {
        model: "machine",
        method: "create_raid",
      },
      payload: {
        params: {
          level: "raid-0",
          name: "raid1",
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a vlan", () => {
    expect(
      actions.createVlan({
        interface_speed: 10,
        ip_address: "1.2.3.4",
        link_connected: true,
        link_speed: 10,
        mode: NetworkLinkMode.AUTO,
        parent: 1,
        system_id: "abc123",
        tags: ["koala", "tag"],
        vlan: 9,
      })
    ).toEqual({
      type: "machine/createVlan",
      meta: {
        model: "machine",
        method: "create_vlan",
      },
      payload: {
        params: {
          interface_speed: 10,
          ip_address: "1.2.3.4",
          link_connected: true,
          link_speed: 10,
          mode: NetworkLinkMode.AUTO,
          parent: 1,
          system_id: "abc123",
          tags: ["koala", "tag"],
          vlan: 9,
        },
      },
    });
  });

  it("can handle creating a VMFS datastore with all params", () => {
    expect(
      actions.createVmfsDatastore({
        blockDeviceIds: [1, 2],
        name: "datastore1",
        partitionIds: [3, 4],
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createVmfsDatastore",
      meta: {
        model: "machine",
        method: "create_vmfs_datastore",
      },
      payload: {
        params: {
          block_devices: [1, 2],
          name: "datastore1",
          partitions: [3, 4],
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a VMFS datastore with only required params", () => {
    expect(
      actions.createVmfsDatastore({
        name: "datastore1",
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createVmfsDatastore",
      meta: {
        model: "machine",
        method: "create_vmfs_datastore",
      },
      payload: {
        params: {
          name: "datastore1",
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle creating a volume group", () => {
    expect(
      actions.createVolumeGroup({
        blockDeviceIds: [1, 2],
        name: "vg1",
        partitionIds: [3, 4],
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/createVolumeGroup",
      meta: {
        model: "machine",
        method: "create_volume_group",
      },
      payload: {
        params: {
          block_devices: [1, 2],
          name: "vg1",
          partitions: [3, 4],
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a cache set", () => {
    expect(
      actions.deleteCacheSet({
        cacheSetId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deleteCacheSet",
      meta: {
        model: "machine",
        method: "delete_cache_set",
      },
      payload: {
        params: {
          cache_set_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a disk", () => {
    expect(
      actions.deleteDisk({
        blockId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deleteDisk",
      meta: {
        model: "machine",
        method: "delete_disk",
      },
      payload: {
        params: {
          block_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a filesystem with all params", () => {
    expect(
      actions.deleteFilesystem({
        blockDeviceId: 1,
        filesystemId: 2,
        partitionId: 3,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deleteFilesystem",
      meta: {
        model: "machine",
        method: "delete_filesystem",
      },
      payload: {
        params: {
          blockdevice_id: 1,
          filesystem_id: 2,
          partition_id: 3,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a filesystem with only required params", () => {
    expect(
      actions.deleteFilesystem({
        filesystemId: 2,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deleteFilesystem",
      meta: {
        model: "machine",
        method: "delete_filesystem",
      },
      payload: {
        params: {
          filesystem_id: 2,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting an interface", () => {
    expect(
      actions.deleteInterface({
        interfaceId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deleteInterface",
      meta: {
        model: "machine",
        method: "delete_interface",
      },
      payload: {
        params: {
          interface_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a partition", () => {
    expect(
      actions.deletePartition({
        partitionId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/deletePartition",
      meta: {
        model: "machine",
        method: "delete_partition",
      },
      payload: {
        params: {
          partition_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle deleting a volume group", () => {
    expect(
      actions.deleteVolumeGroup({
        systemId: "abc123",
        volumeGroupId: 1,
      })
    ).toEqual({
      type: "machine/deleteVolumeGroup",
      meta: {
        model: "machine",
        method: "delete_volume_group",
      },
      payload: {
        params: {
          system_id: "abc123",
          volume_group_id: 1,
        },
      },
    });
  });

  it("can handle mounting a special filesystem", () => {
    expect(
      actions.mountSpecial({
        fstype: "tmpfs",
        mountOptions: "noexec,size=1024k",
        mountPoint: "/path",
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/mountSpecial",
      meta: {
        model: "machine",
        method: "mount_special",
      },
      payload: {
        params: {
          fstype: "tmpfs",
          mount_options: "noexec,size=1024k",
          mount_point: "/path",
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle linking a subnet", () => {
    expect(
      actions.linkSubnet({
        interface_id: 1,
        ip_address: "1.2.3.4",
        link_id: 2,
        mode: NetworkLinkMode.AUTO,
        subnet: 3,
        system_id: "abc123",
      })
    ).toEqual({
      type: "machine/linkSubnet",
      meta: {
        model: "machine",
        method: "link_subnet",
      },
      payload: {
        params: {
          interface_id: 1,
          ip_address: "1.2.3.4",
          link_id: 2,
          mode: NetworkLinkMode.AUTO,
          subnet: 3,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle unlinking a subnet", () => {
    expect(
      actions.unlinkSubnet({
        interfaceId: 1,
        linkId: 2,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/unlinkSubnet",
      meta: {
        model: "machine",
        method: "unlink_subnet",
      },
      payload: {
        params: {
          interface_id: 1,
          link_id: 2,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle unmounting a special filesystem", () => {
    expect(
      actions.unmountSpecial({
        mountPoint: "/path",
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/unmountSpecial",
      meta: {
        model: "machine",
        method: "unmount_special",
      },
      payload: {
        params: {
          mount_point: "/path",
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle unsubscribing from machines", () => {
    expect(actions.unsubscribe(["abc123", "def456"])).toEqual({
      type: "machine/unsubscribe",
      meta: {
        model: "machine",
        method: "unsubscribe",
      },
      payload: {
        params: {
          system_ids: ["abc123", "def456"],
        },
      },
    });
  });

  it("can handle setting a boot disk", () => {
    expect(
      actions.setBootDisk({
        blockId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/setBootDisk",
      meta: {
        model: "machine",
        method: "set_boot_disk",
      },
      payload: {
        params: {
          block_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle updating a disk with all params", () => {
    expect(
      actions.updateDisk({
        blockId: 1,
        fstype: "fat32",
        mountOptions: "noexec",
        mountPoint: "/path",
        name: "disk1",
        systemId: "abc123",
        tags: ["tag1", "tag2"],
      })
    ).toEqual({
      type: "machine/updateDisk",
      meta: {
        model: "machine",
        method: "update_disk",
      },
      payload: {
        params: {
          block_id: 1,
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          name: "disk1",
          system_id: "abc123",
          tags: ["tag1", "tag2"],
        },
      },
    });
  });

  it("can handle updating a disk with only required params", () => {
    expect(
      actions.updateDisk({
        blockId: 1,
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/updateDisk",
      meta: {
        model: "machine",
        method: "update_disk",
      },
      payload: {
        params: {
          block_id: 1,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle updating a filesystem with all params", () => {
    expect(
      actions.updateFilesystem({
        blockId: 1,
        fstype: "fat32",
        mountOptions: "noexec",
        mountPoint: "/path",
        partitionId: 2,
        systemId: "abc123",
        tags: ["tag1", "tag2"],
      })
    ).toEqual({
      type: "machine/updateFilesystem",
      meta: {
        model: "machine",
        method: "update_filesystem",
      },
      payload: {
        params: {
          block_id: 1,
          fstype: "fat32",
          mount_options: "noexec",
          mount_point: "/path",
          partition_id: 2,
          system_id: "abc123",
          tags: ["tag1", "tag2"],
        },
      },
    });
  });

  it("can handle updating a filesystem with only required params", () => {
    expect(
      actions.updateFilesystem({
        systemId: "abc123",
      })
    ).toEqual({
      type: "machine/updateFilesystem",
      meta: {
        model: "machine",
        method: "update_filesystem",
      },
      payload: {
        params: {
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle updating an interface", () => {
    expect(
      actions.updateInterface({
        interface_id: 1,
        enabled: true,
        interface_speed: 10,
        link_connected: true,
        link_speed: 100,
        mac_address: "2a:67:d7:a7:0f:f9",
        name: "ech0",
        numa_node: 1,
        tags: ["tag"],
        vlan: 9,
        system_id: "abc123",
      })
    ).toEqual({
      type: "machine/updateInterface",
      meta: {
        model: "machine",
        method: "update_interface",
      },
      payload: {
        params: {
          interface_id: 1,
          enabled: true,
          interface_speed: 10,
          link_connected: true,
          link_speed: 100,
          mac_address: "2a:67:d7:a7:0f:f9",
          name: "ech0",
          numa_node: 1,
          tags: ["tag"],
          vlan: 9,
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle updating a VMFS datastore", () => {
    expect(
      actions.updateVmfsDatastore({
        blockDeviceIds: [1, 2],
        name: "datastore1",
        partitionIds: [3, 4],
        systemId: "abc123",
        vmfsDatastoreId: 5,
      })
    ).toEqual({
      type: "machine/updateVmfsDatastore",
      meta: {
        model: "machine",
        method: "update_vmfs_datastore",
      },
      payload: {
        params: {
          add_block_devices: [1, 2],
          add_partitions: [3, 4],
          name: "datastore1",
          system_id: "abc123",
          vmfs_datastore_id: 5,
        },
      },
    });
  });

  it("can handle cleaning machines", () => {
    expect(actions.cleanup()).toEqual({
      type: "machine/cleanup",
    });
  });

  it("can handle cleaning up requests", () => {
    expect(actions.cleanupRequest("123456")).toEqual({
      meta: {
        callId: "123456",
        model: "machine",
        unsubscribe: true,
      },
      payload: null,
      type: "machine/cleanupRequest",
    });
  });

  it("can handle removing requests", () => {
    expect(actions.removeRequest("123456")).toEqual({
      meta: {
        callId: "123456",
      },
      payload: null,
      type: "machine/removeRequest",
    });
  });

  it("can handle filter groups", () => {
    expect(actions.filterGroups()).toEqual({
      type: "machine/filterGroups",
      meta: {
        model: "machine",
        method: "filter_groups",
      },
      payload: null,
    });
  });

  it("can handle filter options", () => {
    expect(actions.filterOptions(FilterGroupKey.Owner)).toEqual({
      type: "machine/filterOptions",
      meta: {
        model: "machine",
        method: "filter_options",
      },
      payload: {
        params: {
          group_key: FilterGroupKey.Owner,
        },
      },
    });
  });
});
