/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DiscoveriesManager.
 */

describe("DiscoveriesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the DiscoveriesManager.
  var DiscoveriesManager;
  beforeEach(inject(function($injector) {
    DiscoveriesManager = $injector.get("DiscoveriesManager");
  }));

  it("set requires attributes", function() {
    expect(DiscoveriesManager._pk).toBe("first_seen");
    expect(DiscoveriesManager._batchKey).toBe("first_seen");
    expect(DiscoveriesManager._handler).toBe("discovery");
    expect(DiscoveriesManager._pollEmptyTimeout).toBe(5000);
  });
});
