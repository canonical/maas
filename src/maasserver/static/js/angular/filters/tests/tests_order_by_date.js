/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for filterByFabric.
 */

describe("orderByDate", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the orderByDate.
  var orderByDate;
  beforeEach(inject(function($filter) {
    orderByDate = $filter("orderByDate");
  }));

  it("sorts latest first", function() {
    var obj1 = {
      created: "Wed, 29 Mar. 2017 15:28:35"
    };
    var obj2 = {
      created: "Wed, 29 Mar. 2017 16:28:35"
    };
    var items = [obj1, obj2];
    expect(orderByDate(items, "created")).toEqual([obj2, obj1]);
  });

  it("sorts latest oldest id first", function() {
    var obj1 = {
      id: 0,
      created: "Wed, 29 Mar. 2017 15:28:35"
    };
    var obj2 = {
      id: 1,
      created: "Wed, 29 Mar. 2017 15:28:35"
    };
    var obj3 = {
      id: 2,
      created: "Wed, 29 Mar. 2017 16:28:35"
    };
    var items = [obj1, obj2, obj3];
    expect(orderByDate(items, "created")).toEqual([obj3, obj2, obj1]);
  });
});
