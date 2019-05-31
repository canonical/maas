/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ScriptsManager.
 */

describe("ScriptsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ScriptsManager.
  var ScriptsManager;
  beforeEach(inject(function($injector) {
    ScriptsManager = $injector.get("ScriptsManager");
  }));

  it("set requires attributes", function() {
    expect(ScriptsManager._pk).toBe("id");
    expect(ScriptsManager._handler).toBe("script");
  });
});
