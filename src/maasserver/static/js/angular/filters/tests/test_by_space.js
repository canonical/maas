/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for filterBySpace.
 */

describe("filterBySpace", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterBySpace.
  var filterBySpace;
  beforeEach(inject(function($filter) {
    filterBySpace = $filter("filterBySpace");
  }));

  it("returns empty if undefined space", function() {
    var i,
      subnet,
      subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        space: 0
      };
      subnets.push(subnet);
    }
    expect(filterBySpace(subnets)).toEqual([]);
  });

  it("only returns subnets with space by object", function() {
    var i,
      subnet,
      space_id = 1,
      other_space_id = 2;
    var subnet_spaces = [],
      other_subnet_spaces = [],
      all_subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        space: space_id
      };
      subnet_spaces.push(subnet);
      all_subnets.push(subnet);
    }
    for (i = 0; i < 3; i++) {
      subnet = {
        space: other_space_id
      };
      other_subnet_spaces.push(subnet);
      all_subnets.push(subnet);
    }
    var space = {
      id: space_id
    };
    expect(filterBySpace(all_subnets, space)).toEqual(subnet_spaces);
  });

  it("only returns subnets with space by id", function() {
    var i,
      subnet,
      space_id = 1,
      other_space_id = 2;
    var subnet_spaces = [],
      other_subnet_spaces = [],
      all_subnets = [];
    for (i = 0; i < 3; i++) {
      subnet = {
        space: space_id
      };
      subnet_spaces.push(subnet);
      all_subnets.push(subnet);
    }
    for (i = 0; i < 3; i++) {
      subnet = {
        space: other_space_id
      };
      other_subnet_spaces.push(subnet);
      all_subnets.push(subnet);
    }
    expect(filterBySpace(all_subnets, space_id)).toEqual(subnet_spaces);
  });
});
