/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for EventsManagerFactory.
 */

import { makeInteger } from "testing/utils";

describe("EventsManagerFactory", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $q, $rootScope;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
    $rootScope = $injector.get("$rootScope");
  }));

  // Load the EventsManagerFactory and RegionConnection.
  var EventsManagerFactory, RegionConnection;
  beforeEach(inject(function($injector) {
    EventsManagerFactory = $injector.get("EventsManagerFactory");
    RegionConnection = $injector.get("RegionConnection");
  }));

  describe("_getManager", function() {
    it("returns null when no manager with nodeId exists", function() {
      expect(EventsManagerFactory._getManager(0)).toBeNull();
    });

    it("returns object from _managers with nodeId", function() {
      var nodeId = makeInteger(0, 100);
      var fakeManager = {
        _nodeId: nodeId
      };
      EventsManagerFactory._managers.push(fakeManager);
      expect(EventsManagerFactory._getManager(nodeId)).toBe(fakeManager);
    });
  });

  describe("getManager", function() {
    it("returns new manager with nodeId doesnt exists", function() {
      var nodeId = makeInteger(0, 100);
      var manager = EventsManagerFactory.getManager(nodeId);
      expect(manager._nodeId).toBe(nodeId);
      expect(EventsManagerFactory._managers).toEqual([manager]);
    });

    it("returns same manager with nodeId exists", function() {
      var nodeId = makeInteger(0, 100);
      var manager = EventsManagerFactory.getManager(nodeId);
      expect(EventsManagerFactory.getManager(nodeId)).toBe(manager);
    });
  });

  describe("destroyManager", function() {
    it("removes manager from _managers", function() {
      var nodeId = makeInteger(0, 100);
      var manager = EventsManagerFactory.getManager(nodeId);
      EventsManagerFactory.destroyManager(manager);
      expect(EventsManagerFactory._managers).toEqual([]);
    });
  });

  describe("onNotify", function() {
    it("sends delete notification to all managers", function() {
      var i,
        id = 0;
      var managers = [];
      for (i = 0; i < 3; i++) {
        var manager = EventsManagerFactory.getManager(id++);
        spyOn(manager, "onNotify");
        managers.push(manager);
      }
      var deleteId = makeInteger(0, 100);
      EventsManagerFactory.onNotify("delete", deleteId);
      angular.forEach(managers, function(manager) {
        expect(manager.onNotify).toHaveBeenCalledWith("delete", deleteId);
      });
    });

    it("sends create notification to manager with nodeId", function() {
      var i,
        id = 0;
      var otherManagers = [];
      for (i = 0; i < 3; i++) {
        var manager = EventsManagerFactory.getManager(id++);
        spyOn(manager, "onNotify");
        otherManagers.push(manager);
      }
      var calledManager = EventsManagerFactory.getManager(id);
      spyOn(calledManager, "onNotify");
      var evt = {
        node_id: id
      };
      EventsManagerFactory.onNotify("create", evt);
      angular.forEach(otherManagers, function(manager) {
        expect(manager.onNotify).not.toHaveBeenCalled();
      });
      expect(calledManager.onNotify).toHaveBeenCalledWith("create", evt);
    });

    it("sends update notification to manager with nodeId", function() {
      var i,
        id = 0;
      var otherManagers = [];
      for (i = 0; i < 3; i++) {
        var manager = EventsManagerFactory.getManager(id++);
        spyOn(manager, "onNotify");
        otherManagers.push(manager);
      }
      var calledManager = EventsManagerFactory.getManager(id);
      spyOn(calledManager, "onNotify");
      var evt = {
        node_id: id
      };
      EventsManagerFactory.onNotify("update", evt);
      angular.forEach(otherManagers, function(manager) {
        expect(manager.onNotify).not.toHaveBeenCalled();
      });
      expect(calledManager.onNotify).toHaveBeenCalledWith("update", evt);
    });
  });

  describe("EventsManager", function() {
    var nodeId, eventManager;
    beforeEach(function() {
      nodeId = makeInteger(0, 100);
      eventManager = EventsManagerFactory.getManager(nodeId);
    });

    it("sets required attributes", function() {
      expect(eventManager._pk).toBe("id");
      expect(eventManager._handler).toBe("event");
      expect(eventManager._nodeId).toBe(nodeId);
      expect(eventManager._handler).toBe("event");
      expect(eventManager._factory).toBe(EventsManagerFactory);
      expect(eventManager._maxDays).toBe(1);
    });

    describe("_initBatchLoadParameters", function() {
      it("returns parameters with node_id and max_days", function() {
        expect(eventManager._initBatchLoadParameters()).toEqual({
          node_id: nodeId,
          max_days: 1
        });
      });
    });

    describe("destroy", function() {
      it("calls _factory.destroyManager", function() {
        spyOn(EventsManagerFactory, "destroyManager");
        eventManager.destroy();
        expect(EventsManagerFactory.destroyManager).toHaveBeenCalledWith(
          eventManager
        );
      });

      it("calls event.clear on the RegionConnection if loaded", function() {
        spyOn(eventManager, "isLoaded").and.returnValue(true);
        spyOn(RegionConnection, "callMethod");
        eventManager.destroy();
        expect(RegionConnection.callMethod).toHaveBeenCalledWith(
          "event.clear",
          { node_id: nodeId }
        );
      });
    });

    describe("getMaximumDays", function() {
      it("returns _maxDays", function() {
        var sentinel = {};
        eventManager._maxDays = sentinel;
        expect(eventManager.getMaximumDays()).toBe(sentinel);
      });
    });

    describe("loadMaximumDays", function() {
      it("sets _maxDays and calls loadItems", function() {
        var maxDays = makeInteger(30, 90);
        spyOn(eventManager, "loadItems");
        eventManager.loadMaximumDays(maxDays);
        expect(eventManager._maxDays).toBe(maxDays);
        expect(eventManager.loadItems).toHaveBeenCalled();
      });

      it("doesnt sets _maxDays until loadItems resolves", function() {
        var maxDays = makeInteger(31, 90);
        var defer = $q.defer();
        spyOn(eventManager, "loadItems").and.returnValue(defer.promise);
        spyOn(eventManager, "isLoading").and.returnValue(true);
        eventManager.loadMaximumDays(maxDays);
        expect(eventManager._maxDays).toBe(1);

        defer.resolve();
        $rootScope.$digest();

        expect(eventManager._maxDays).toBe(maxDays);
        expect(eventManager.loadItems.calls.count()).toBe(2);
      });
    });
  });
});
