/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ConfigsManager.
 */

describe("ConfigsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ConfigsManager.
  var ConfigsManager;
  beforeEach(inject(function($injector) {
    ConfigsManager = $injector.get("ConfigsManager");
  }));

  it("set requires attributes", function() {
    expect(ConfigsManager._pk).toBe("name");
    expect(ConfigsManager._handler).toBe("config");
  });
});
