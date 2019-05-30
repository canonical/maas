/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for removeDefaultVLAN.
 */

describe("removeDefaultVLAN", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the removeDefaultVLAN.
  var removeDefaultVLAN;
  beforeEach(inject(function($filter) {
    removeDefaultVLAN = $filter("removeDefaultVLAN");
  }));

  it("only returns vlans without vid 0", function() {
    var i,
      vlan,
      vlans = [];
    for (i = 0; i < 3; i++) {
      vlan = {
        id: i,
        vid: i,
        fabric: 0
      };
      vlans.push(vlan);
    }
    expect(removeDefaultVLAN(vlans)).toEqual([vlans[1], vlans[2]]);
  });
});
