/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ResourcePoolsManager.
 */

import { makeInteger, makeName } from "testing/utils";

describe("ResourcePoolsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ResourcePoolsManager.
  var ResourcePoolsManager;
  beforeEach(inject(function($injector) {
    ResourcePoolsManager = $injector.get("ResourcePoolsManager");
  }));

  function makeResourcePool(id) {
    var pool = {
      name: makeName("name")
    };
    if (angular.isDefined(id)) {
      pool.id = id;
    } else {
      pool.id = makeInteger(1, 100);
    }
    return pool;
  }

  it("set requires attributes", function() {
    expect(ResourcePoolsManager._pk).toBe("id");
    expect(ResourcePoolsManager._handler).toBe("resourcepool");
  });

  it("getDefaultPool returns pool with id = 0", function() {
    var defaultPool = makeResourcePool(0);
    ResourcePoolsManager._items.push(makeResourcePool());
    ResourcePoolsManager._items.push(defaultPool);
    expect(ResourcePoolsManager.getDefaultPool()).toBe(defaultPool);
  });
});
