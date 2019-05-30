/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for IPRangesManager.
 */

describe("IPRangesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the IPRangesManager.
  var IPRangesManager;
  beforeEach(inject(function($injector) {
    IPRangesManager = $injector.get("IPRangesManager");
  }));

  it("set requires attributes", function() {
    expect(IPRangesManager._pk).toBe("id");
    expect(IPRangesManager._handler).toBe("iprange");
  });
});
