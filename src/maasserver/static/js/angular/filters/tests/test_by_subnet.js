/* Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for by_subnet filters.
 */

describe("filterBySubnet", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load filterBySubnet function.
  var filterBySubnet;
  beforeEach(inject(function($filter) {
    filterBySubnet = $filter("filterBySubnet");
  }));

  it("returns an empty list for a null subnet", function() {
    expect(filterBySubnet([], null)).toEqual([]);
  });

  it("does not match unrelated object", function() {
    var subnet = { id: 1 };
    var foreign_object = { subnet: 0 };
    expect(filterBySubnet([foreign_object], subnet)).toEqual([]);
  });

  it("matches related object", function() {
    var subnet = { id: 1 };
    var foreign_object = { subnet: 1 };
    expect(filterBySubnet([foreign_object], subnet)).toEqual([foreign_object]);
  });

  it("matches related objects", function() {
    var subnet = { id: 1 };
    var foreign1 = { subnet: 0 };
    var foreign2 = { subnet: 1 };
    expect(filterBySubnet([foreign1, foreign2], subnet)).toEqual([foreign2]);
  });

  it("matches related objects by id", function() {
    var subnet = { id: 1 };
    var foreign1 = { subnet: 0 };
    var foreign2 = { subnet: 1 };
    expect(filterBySubnet([foreign1, foreign2], subnet.id)).toEqual([foreign2]);
  });

  it("matches multiple related objects", function() {
    var subnet = { id: 1 };
    var foreign1 = { subnet: 1 };
    var foreign2 = { subnet: 0 };
    var foreign3 = { subnet: 1 };
    expect(filterBySubnet([foreign1, foreign2, foreign3], subnet)).toEqual([
      foreign1,
      foreign3
    ]);
  });
});

describe("filterBySubnetOrVlan", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load filterBySubnet function.
  var filterBySubnetOrVlan;
  beforeEach(inject(function($filter) {
    filterBySubnetOrVlan = $filter("filterBySubnetOrVlan");
  }));

  it("returns an empty list for a null subnet", function() {
    expect(filterBySubnetOrVlan([], null)).toEqual([]);
  });

  it("returns an empty list for a null vlan", function() {
    expect(filterBySubnetOrVlan([], null, null)).toEqual([]);
  });

  it("does not match unrelated object", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign_object = { subnet: 0, vlan: 1 };
    expect(filterBySubnetOrVlan([foreign_object], subnet, vlan)).toEqual([]);
  });

  it("matches related subnet", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign_object = { subnet: 1 };
    expect(filterBySubnetOrVlan([foreign_object], subnet, vlan)).toEqual([
      foreign_object
    ]);
  });

  it("matches related vlan", function() {
    var vlan = { id: 2 };
    var foreign_object = { vlan: 2 };
    expect(filterBySubnetOrVlan([foreign_object], null, vlan)).toEqual([
      foreign_object
    ]);
  });

  it("matches related subnets", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign1 = { subnet: 0 };
    var foreign2 = { subnet: 1 };
    var foreign3 = { vlan: 2 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], subnet, vlan)
    ).toEqual([foreign2]);
  });

  it("matches related vlans", function() {
    var vlan = { id: 2 };
    var foreign1 = { subnet: 0 };
    var foreign2 = { subnet: 1, vlan: 2 };
    var foreign3 = { vlan: 2 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], null, vlan)
    ).toEqual([foreign2, foreign3]);
  });

  it("matches related subnets by id", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign1 = { subnet: 0 };
    var foreign2 = { subnet: 1 };
    var foreign3 = { subnet: 1 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], subnet.id, vlan.id)
    ).toEqual([foreign2, foreign3]);
  });

  it("matches related vlans by id", function() {
    var vlan = { id: 2 };
    var foreign1 = { subnet: 0, vlan: 1 };
    var foreign2 = { subnet: 1, vlan: 2 };
    var foreign3 = { subnet: 1, vlan: 2 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], null, vlan.id)
    ).toEqual([foreign2, foreign3]);
  });

  it("matches multiple related subnets", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign1 = { subnet: 1 };
    var foreign2 = { subnet: 0 };
    var foreign3 = { subnet: 1 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], subnet, vlan)
    ).toEqual([foreign1, foreign3]);
  });

  it("matches multiple related vlans", function() {
    var subnet = { id: 1 };
    var vlan = { id: 2 };
    var foreign1 = { subnet: 1, vlan: 2 };
    var foreign2 = { subnet: 0, vlan: 1 };
    var foreign3 = { subnet: 1, vlan: 2 };
    expect(
      filterBySubnetOrVlan([foreign1, foreign2, foreign3], subnet, vlan)
    ).toEqual([foreign1, foreign3]);
  });
});
