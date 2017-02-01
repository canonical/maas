/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NotificationsManager.
 */

describe("NotificationsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the NotificationsManager and RegionConnection.
    var NotificationsManager;
    var RegionConnection;
    beforeEach(inject(function($injector) {
        RegionConnection = $injector.get("RegionConnection");
        spyOn(RegionConnection, "registerNotifier");
        NotificationsManager = $injector.get("NotificationsManager");
    }));

    // Make a random notification.
    function makeNotification(id, selected) {
        var notification = {
            name: makeName("name"),
            authoritative: true
        };
        if(angular.isDefined(id)) {
            notification.id = id;
        } else {
            notification.id = makeInteger(1, 100);
        }
        if(angular.isDefined(selected)) {
            notification.$selected = selected;
        }
        return notification;
    }

    it("set requires attributes", function() {
        expect(NotificationsManager._pk).toBe("id");
        expect(NotificationsManager._handler).toBe("notification");
    });

    it("listens for updates", function() {
        expect(RegionConnection.registerNotifier).toHaveBeenCalled();
    });

});
