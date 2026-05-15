import { actions } from "./slice";

import { NodeActions } from "@/app/store/types/node";

describe("controller actions", () => {
  it("should handle checking images", () => {
    expect(actions.checkImages(["abc123", "def456"])).toEqual({
      type: "controller/checkImages",
      meta: {
        model: "controller",
        method: "check_images",
      },
      payload: { params: [{ system_id: "abc123" }, { system_id: "def456" }] },
    });
  });

  it("should handle polling checking images", () => {
    expect(actions.pollCheckImages(["abc123", "def456"], "pollid123")).toEqual({
      type: "controller/pollCheckImages",
      meta: {
        model: "controller",
        method: "check_images",
        poll: true,
        pollId: "pollid123",
        pollInterval: 30000,
      },
      payload: { params: [{ system_id: "abc123" }, { system_id: "def456" }] },
    });
  });

  it("should handle stop polling checking images", () => {
    expect(actions.pollCheckImagesStop("pollid123")).toEqual({
      type: "controller/pollCheckImagesStop",
      meta: {
        model: "controller",
        method: "check_images",
        pollId: "pollid123",
        pollStop: true,
      },
      payload: null,
    });
  });

  it("should handle fetching controllers", () => {
    expect(actions.fetch()).toEqual({
      type: "controller/fetch",
      meta: {
        model: "controller",
        method: "list",
      },
      payload: null,
    });
  });

  it("should handle creating controllers", () => {
    expect(
      actions.create({
        description: "a controller",
      })
    ).toEqual({
      type: "controller/create",
      meta: {
        model: "controller",
        method: "create",
      },
      payload: {
        params: {
          description: "a controller",
        },
      },
    });
  });

  it("should handle updating controllers", () => {
    expect(
      actions.update({
        system_id: "abc123",
        description: "an updated controller",
      })
    ).toEqual({
      type: "controller/update",
      meta: {
        model: "controller",
        method: "update",
      },
      payload: {
        params: {
          system_id: "abc123",
          description: "an updated controller",
        },
      },
    });
  });

  it("can get a controller", () => {
    expect(actions.get("abc123")).toEqual({
      type: "controller/get",
      meta: {
        model: "controller",
        method: "get",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can set an active controller", () => {
    expect(actions.setActive("abc123")).toEqual({
      type: "controller/setActive",
      meta: {
        model: "controller",
        method: "set_active",
      },
      payload: {
        params: { system_id: "abc123" },
      },
    });
  });

  it("can handle deleting a controller", () => {
    expect(actions.delete({ system_id: "abc123" })).toEqual({
      type: "controller/delete",
      meta: {
        model: "controller",
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

  it("can handle setting selected controllers", () => {
    expect(actions.setSelected(["abc123", "def456"])).toEqual({
      type: "controller/setSelected",
      payload: ["abc123", "def456"],
    });
  });

  it("can handle setting the zone", () => {
    expect(actions.setZone({ system_id: "abc123", zone_id: 909 })).toEqual({
      type: "controller/setZone",
      meta: {
        model: "controller",
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

  it("can handle turning on the controller", () => {
    expect(actions.on({ system_id: "abc123" })).toEqual({
      type: "controller/on",
      meta: {
        model: "controller",
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

  it("can handle turning off the controller", () => {
    expect(actions.off({ system_id: "abc123" })).toEqual({
      type: "controller/off",
      meta: {
        model: "controller",
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

  it("can handle testing a controller", () => {
    expect(
      actions.test({
        enable_ssh: true,
        script_input: { "test-0": { url: "www.url.com" } },
        system_id: "abc123",
        testing_scripts: ["test0", "test2"],
      })
    ).toEqual({
      type: "controller/test",
      meta: {
        model: "controller",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.TEST,
          extra: {
            enable_ssh: true,
            script_input: { "test-0": { url: "www.url.com" } },
            testing_scripts: ["test0", "test2"],
          },
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle overriding failed testing on a controller", () => {
    expect(actions.overrideFailedTesting({ system_id: "abc123" })).toEqual({
      type: "controller/overrideFailedTesting",
      meta: {
        model: "controller",
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

  it("can handle importing images", () => {
    expect(actions.importImages({ system_id: "abc123" })).toEqual({
      type: "controller/importImages",
      meta: {
        model: "controller",
        method: "action",
      },
      payload: {
        params: {
          action: NodeActions.IMPORT_IMAGES,
          extra: {},
          system_id: "abc123",
        },
      },
    });
  });

  it("can handle getting a summary XML file", () => {
    expect(
      actions.getSummaryXml({ systemId: "abc123", fileId: "file1" })
    ).toEqual({
      type: "controller/getSummaryXml",
      meta: {
        fileContextKey: "file1",
        model: "controller",
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
      type: "controller/getSummaryYaml",
      meta: {
        fileContextKey: "file1",
        model: "controller",
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
});
