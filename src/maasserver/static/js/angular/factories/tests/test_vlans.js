/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for VLANsManager.
 */

import { makeInteger } from "testing/utils";

describe("VLANsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the VLANsManager.
  var VLANsManager, RegionConnection;
  beforeEach(inject(function($injector) {
    VLANsManager = $injector.get("VLANsManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(VLANsManager._pk).toBe("id");
    expect(VLANsManager._handler).toBe("vlan");
  });

  describe("configureDHCP", function() {
    it("calls the region with expected parameters", function() {
      var obj = { id: makeInteger(1, 1000) };
      var result = {};
      var controllers = ["a", "b"];
      var extra = { c: "d" };
      var relay = makeInteger(1, 500);
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(VLANsManager.configureDHCP(obj, controllers, extra, relay)).toBe(
        result
      );
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "vlan.configure_dhcp",
        {
          id: obj.id,
          controllers: controllers,
          extra: extra,
          relay_vlan: relay
        },
        true
      );
    });
  });

  describe("disableDHCP", function() {
    it("calls the region with expected parameters", function() {
      var obj = { id: makeInteger(1, 1000) };
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(VLANsManager.disableDHCP(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "vlan.configure_dhcp",
        {
          id: obj.id,
          controllers: [],
          relay_vlan: null
        },
        true
      );
    });
  });

  describe("create", function() {
    it("calls the region with expected parameters", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(VLANsManager.create(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "vlan.create",
        obj
      );
    });
  });

  describe("delete", function() {
    it("calls the region with expected parameters", function() {
      var obj = { id: "whatever" };
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(VLANsManager.deleteVLAN(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "vlan.delete",
        obj,
        true
      );
    });
  });
});
