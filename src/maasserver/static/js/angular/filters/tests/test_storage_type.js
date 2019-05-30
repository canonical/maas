/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for formatStorageType.
 */

describe("formatStorageType", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the storageType.
  var storageType;
  beforeEach(inject(function($filter) {
    storageType = $filter("formatStorageType");
  }));

  it("returns empty string if undefined storage type", function() {
    expect(storageType()).toEqual("");
  });

  it("returns original value if not recognised", function() {
    expect(storageType("foo")).toEqual("foo");
  });

  it("returns formatted when recognised", function() {
    expect(storageType("lvm")).toEqual("LVM");
  });
});
