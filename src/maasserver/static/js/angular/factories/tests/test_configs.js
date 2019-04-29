/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ConfigsManager.
 */

describe("ConfigsManager", function() {
  // Load the MAAS module.
  beforeEach(module("MAAS"));

  // Load the ConfigsManager.
  var ConfigsManager, RegionConnection;
  beforeEach(inject(function($injector) {
    ConfigsManager = $injector.get("ConfigsManager");
    RegionConnection = $injector.get("RegionConnection");
  }));

  it("set requires attributes", function() {
    expect(ConfigsManager._pk).toBe("name");
    expect(ConfigsManager._handler).toBe("config");
  });
});
