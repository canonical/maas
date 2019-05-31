/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SpacesManager.
 */

describe("SpacesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the SpacesManager.
  var SpacesManager, RegionConnection;
  beforeEach(inject(function($injector) {
    SpacesManager = $injector.get("SpacesManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(SpacesManager._pk).toBe("id");
    expect(SpacesManager._handler).toBe("space");
  });

  describe("create", function() {
    it("calls the region with expected parameters", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SpacesManager.create(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "space.create",
        obj
      );
    });
  });

  describe("delete", function() {
    it("calls the region with expected parameters", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SpacesManager.deleteSpace(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "space.delete",
        obj
      );
    });
  });
});
