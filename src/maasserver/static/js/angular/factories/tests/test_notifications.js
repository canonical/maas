/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NotificationsManager.
 */

describe("NotificationsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the NotificationsManager and RegionConnection.
  var NotificationsManager;
  var RegionConnection;
  beforeEach(inject(function($injector) {
    RegionConnection = $injector.get("RegionConnection");
    spyOn(RegionConnection, "registerNotifier");
    NotificationsManager = $injector.get("NotificationsManager");
  }));

  it("set requires attributes", function() {
    expect(NotificationsManager._pk).toBe("id");
    expect(NotificationsManager._handler).toBe("notification");
  });

  it("listens for updates", function() {
    expect(RegionConnection.registerNotifier).toHaveBeenCalled();
  });
});
