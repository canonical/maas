/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for TagsManager.
 */

describe("TagsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the TagsManager.
  var TagsManager;
  beforeEach(inject(function($injector) {
    TagsManager = $injector.get("TagsManager");
  }));

  it("set requires attributes", function() {
    expect(TagsManager._pk).toBe("id");
    expect(TagsManager._handler).toBe("tag");
  });

  describe("autocomplete", function() {
    it("returns array of matching tags", function() {
      var tags = ["apple", "banana", "cake", "donut"];
      angular.forEach(tags, function(tag) {
        TagsManager._items.push({ name: tag });
      });
      expect(TagsManager.autocomplete("a")).toEqual([
        "apple",
        "banana",
        "cake"
      ]);
      expect(TagsManager.autocomplete("do")).toEqual(["donut"]);
    });
  });
});
