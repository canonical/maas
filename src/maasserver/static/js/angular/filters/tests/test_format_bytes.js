/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for formatBytes.
 */

describe("formatBytes", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the formatBytes.
  var formatBytes;
  beforeEach(inject(function($filter) {
    formatBytes = $filter("formatBytes");
  }));

  it("returns zero if undefined bytes", function() {
    expect(formatBytes()).toEqual(0);
  });

  it("returns value in bytes if less than a kilobyte", function() {
    expect(formatBytes(456)).toEqual("456 B");
  });

  it("returns value in kilobytes if less than a megabyte", function() {
    expect(formatBytes(568000000)).toEqual("568 MB");
  });

  it("returns value in gigabytes if less than a terabyte", function() {
    expect(formatBytes(382000000000)).toEqual("382 GB");
  });

  it(`returns value in terabytes if greater than
      or equal to 1 terabyte, to 3 significant figures`, function() {
    expect(formatBytes(2000000000000)).toEqual("2.00 TB");
  });
});
