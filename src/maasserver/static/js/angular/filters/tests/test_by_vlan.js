/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for filterByVLAN.
 */

describe("filterByVLAN", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterByVLAN.
  var filterByVLAN;
  beforeEach(inject(function($filter) {
    filterByVLAN = $filter("filterByVLAN");
  }));

  it("returns empty if undefined space", function() {
    var i,
      subnet,
      subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        vlan: 0
      };
      subnets.push(subnet);
    }
    expect(filterByVLAN(subnets)).toEqual([]);
  });

  it("only returns subnets with vlan by object", function() {
    var i,
      subnet,
      vlan_id = 1,
      other_vlan_id = 2;
    var subnet_vlans = [],
      other_subnet_vlans = [],
      all_subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        vlan: vlan_id
      };
      subnet_vlans.push(subnet);
      all_subnets.push(subnet);
    }
    for (i = 0; i < 3; i++) {
      subnet = {
        vlan: other_vlan_id
      };
      other_subnet_vlans.push(subnet);
      all_subnets.push(subnet);
    }
    var vlan = {
      id: vlan_id
    };
    expect(filterByVLAN(all_subnets, vlan)).toEqual(subnet_vlans);
  });

  it("only returns subnets with vlan by id", function() {
    var i,
      subnet,
      vlan_id = 1,
      other_vlan_id = 2;
    var subnet_vlans = [],
      other_subnet_vlans = [],
      all_subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        vlan: vlan_id
      };
      subnet_vlans.push(subnet);
      all_subnets.push(subnet);
    }
    for (i = 0; i < 3; i++) {
      subnet = {
        vlan: other_vlan_id
      };
      other_subnet_vlans.push(subnet);
      all_subnets.push(subnet);
    }
    expect(filterByVLAN(all_subnets, vlan_id)).toEqual(subnet_vlans);
  });
});
