/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for StaticRoutesManager.
 */

describe("StaticRoutesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the StaticRoutesManager.
  var StaticRoutesManager;
  beforeEach(inject(function($injector) {
    StaticRoutesManager = $injector.get("StaticRoutesManager");
  }));

  it("set requires attributes", function() {
    expect(StaticRoutesManager._pk).toBe("id");
    expect(StaticRoutesManager._handler).toBe("staticroute");
  });
});
