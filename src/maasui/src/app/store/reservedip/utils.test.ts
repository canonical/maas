import { NodeType } from "../types/node";

import { getNodeUrl } from "./utils";

describe("getNodeUrl", () => {
  it("gets the URL for a machine", () => {
    expect(getNodeUrl(NodeType.MACHINE, "abc123")).toBe("/machine/abc123");
  });

  it("gets the URL for a device", () => {
    expect(getNodeUrl(NodeType.DEVICE, "abc123")).toBe("/device/abc123");
  });

  it("gets the URL for a rack controller", () => {
    expect(getNodeUrl(NodeType.RACK_CONTROLLER, "abc123")).toBe(
      "/controller/abc123"
    );
  });

  it("gets the URL for a region controller", () => {
    expect(getNodeUrl(NodeType.REGION_CONTROLLER, "abc123")).toBe(
      "/controller/abc123"
    );
  });

  it("gets the URL for a region + rack controller", () => {
    expect(getNodeUrl(NodeType.REGION_AND_RACK_CONTROLLER, "abc123")).toBe(
      "/controller/abc123"
    );
  });
});
