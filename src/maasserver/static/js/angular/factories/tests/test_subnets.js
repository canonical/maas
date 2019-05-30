/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubnetsManager.
 */

describe("SubnetsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the SubnetsManager.
  var SubnetsManager, RegionConnection;
  beforeEach(inject(function($injector) {
    SubnetsManager = $injector.get("SubnetsManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(SubnetsManager._pk).toBe("id");
    expect(SubnetsManager._handler).toBe("subnet");
  });

  describe("getName", function() {
    it("returns empty string if no object is passed in", function() {
      expect(SubnetsManager.getName()).toBe("");
    });

    it("returns cidr only if name equals cidr", function() {
      var subnet = {
        cidr: "169.254.0.0/16",
        name: "169.254.0.0/16"
      };
      expect(SubnetsManager.getName(subnet)).toBe("169.254.0.0/16");
    });

    it("returns cidr only if name does not exist", function() {
      var subnet = {
        cidr: "169.254.0.0/16"
      };
      expect(SubnetsManager.getName(subnet)).toBe("169.254.0.0/16");
    });

    it("returns cidr only if name is an empty string", function() {
      var subnet = {
        cidr: "169.254.0.0/16",
        name: ""
      };
      expect(SubnetsManager.getName(subnet)).toBe("169.254.0.0/16");
    });

    it("returns cidr with parenthetical name if name exists", function() {
      var subnet = {
        cidr: "169.254.0.0/16",
        name: "name"
      };
      expect(SubnetsManager.getName(subnet)).toBe("169.254.0.0/16 (name)");
    });
  });

  describe("create", function() {
    it("calls the region with expected parameters", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SubnetsManager.create(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "subnet.create",
        obj
      );
    });
  });

  describe("delete", function() {
    it("calls the region with expected parameters", function() {
      var obj = { id: "expected", not_the_id: "unexpected" };
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SubnetsManager.deleteSubnet(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "subnet.delete",
        { id: "expected" }
      );
    });
  });

  describe("scan", function() {
    it("calls the region with expected parameters", function() {
      var obj = { id: "expected", not_the_id: "unexpected" };
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SubnetsManager.scanSubnet(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith("subnet.scan", {
        id: "expected"
      });
    });
  });
});
