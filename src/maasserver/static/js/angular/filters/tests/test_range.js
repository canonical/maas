/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for filterRange.
 */

describe("filterRange", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the filterRange.
  var filterRange;
  beforeEach(inject(function($filter) {
    filterRange = $filter("range");
  }));

  it("returns empty if invalid range", function() {
    var array = undefined;
    expect(filterRange(array)).toEqual([]);
  });

  it("returns correct length array", function() {
    var i = 3;
    var len = filterRange(i).length;
    expect(len).toEqual(i);
  });
});
