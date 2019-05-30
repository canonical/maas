/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SSHKeysManager.
 */

describe("SSHKeysManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the SSHKeysManager.
  var SSHKeysManager, RegionConnection;
  beforeEach(inject(function($injector) {
    SSHKeysManager = $injector.get("SSHKeysManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(SSHKeysManager._pk).toBe("id");
    expect(SSHKeysManager._handler).toBe("sshkey");
  });

  describe("importKeys", function() {
    it("calls the region", function() {
      var obj = {};
      var result = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(result);
      expect(SSHKeysManager.importKeys(obj)).toBe(result);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "sshkey.import_keys",
        obj
      );
    });
  });
});
