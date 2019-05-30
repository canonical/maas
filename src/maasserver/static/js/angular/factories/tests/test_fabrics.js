/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for FabricsManager.
 */

import { makeInteger } from "testing/utils";

describe("FabricsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the FabricsManager.
  var FabricsManager, RegionConnection;
  beforeEach(inject(function($injector) {
    FabricsManager = $injector.get("FabricsManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(FabricsManager._pk).toBe("id");
    expect(FabricsManager._handler).toBe("fabric");
  });

  describe("getName", function() {
    it("returns undefined if no object is passed in", function() {
      expect(FabricsManager.getName()).toBe(undefined);
    });

    it("returns name if name exists", function() {
      var fabric = {
        name: "jury-rigged"
      };
      expect(FabricsManager.getName(fabric)).toBe("jury-rigged");
    });

    it("returns name if name is null", function() {
      var fabric = {
        id: makeInteger(0, 1000),
        name: null
      };
      expect(FabricsManager.getName(fabric)).toBe("fabric-" + fabric.id);
    });
  });

  describe("create", function() {
    it("calls the region with expected parameters", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(FabricsManager.create(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "fabric.create",
        obj
      );
    });
  });
});
