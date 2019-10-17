/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ZonesManager.
 */

import { makeInteger, makeName } from "testing/utils";

describe("ZonesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ZonesManager.
  var ZonesManager;
  beforeEach(inject(function($injector) {
    ZonesManager = $injector.get("ZonesManager");
  }));

  function makeZone(id) {
    var zone = {
      name: makeName("name")
    };
    if (angular.isDefined(id)) {
      zone.id = id;
    } else {
      zone.id = makeInteger(1, 100);
    }
    return zone;
  }

  it("set requires attributes", function() {
    expect(ZonesManager._pk).toBe("id");
    expect(ZonesManager._handler).toBe("zone");
  });

  describe("getDefaultZone", function() {
    it("returns null when no domains", function() {
      expect(ZonesManager.getDefaultZone()).toBe(null);
    });

    it("returns domain with id = 0", function() {
      var zero = makeZone(0);
      ZonesManager._items.push(makeZone());
      ZonesManager._items.push(zero);
      expect(ZonesManager.getDefaultZone()).toBe(zero);
    });

    it("returns first domain otherwise", function() {
      var i;
      for (i = 0; i < 3; i++) {
        ZonesManager._items.push(makeZone());
      }
      expect(ZonesManager.getDefaultZone()).toBe(ZonesManager._items[0]);
    });

    it("returns correct zone if optional pod is passed", function() {
      var i;
      for (i = 0; i < 3; i++) {
        const zone = makeZone(i);
        zone.name = `test-zone-${i}`;
        ZonesManager._items.push(zone);
      }
      expect(
        ZonesManager.getDefaultZone({
          zone: ZonesManager._items[2].id
        })
      ).toBe(ZonesManager._items[2]);
    });
  });
});
