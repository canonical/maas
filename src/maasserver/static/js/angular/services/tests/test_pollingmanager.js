/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for PollingManager.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("PollingManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $rootScope, $timeout, $q;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $timeout = $injector.get("$timeout");
    $q = $injector.get("$q");
  }));

  // Load the PollingManager and RegionConnection factory.
  var TestManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    var PollingManager = $injector.get("PollingManager");
    RegionConnection = $injector.get("RegionConnection");

    // Create a fake manager
    function FakeManager() {
      PollingManager.call(this);
      this._pk = "id";
      this._handler = "fake";
    }
    FakeManager.prototype = new PollingManager();
    TestManager = new FakeManager();

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Open the connection to the region before each test.
  beforeEach(function(done) {
    RegionConnection.registerHandler("open", function() {
      done();
    });
    RegionConnection.connect("");
  });

  it("sets initial values", function() {
    expect(TestManager._type).toBe("poll");
    expect(TestManager._polling).toBe(false);
    expect(TestManager._nextPromise).toBeNull();
    expect(TestManager._pollTimeout).toBe(10000);
    expect(TestManager._pollErrorTimeout).toBe(3000);
    expect(TestManager._pollEmptyTimeout).toBe(3000);
  });

  describe("isPolling", function() {
    it("returns _polling", function() {
      var sentinel = {};
      TestManager._polling = sentinel;
      expect(TestManager.isPolling()).toBe(sentinel);
    });
  });

  describe("startPolling", function() {
    it("calls _poll and sets polling", function() {
      var sentinel = {};
      spyOn(TestManager, "_poll").and.returnValue(sentinel);
      expect(TestManager.startPolling()).toBe(sentinel);
      expect(TestManager._polling).toBe(true);
    });

    it("returns _nextPromise if already polling", function() {
      var sentinel = {};
      TestManager._polling = true;
      TestManager._nextPromise = sentinel;
      spyOn(TestManager, "_poll");
      expect(TestManager.startPolling()).toBe(sentinel);
      expect(TestManager._poll).not.toHaveBeenCalled();
    });
  });

  describe("stopPolling", function() {
    it("clears _polling and cancels _nextPromise", function() {
      var sentinel = {};
      TestManager._polling = true;
      TestManager._nextPromise = sentinel;
      spyOn($timeout, "cancel");
      TestManager.stopPolling();
      expect($timeout.cancel).toHaveBeenCalledWith(sentinel);
      expect(TestManager._nextPromise).toBeNull();
      expect(TestManager._polling).toBe(false);
    });
  });

  describe("_pollAgain", function() {
    it("sets _nextPromise and calls _poll after timeout", function() {
      spyOn(TestManager, "_poll");
      TestManager._pollAgain(1);

      expect(TestManager._nextPromise).not.toBeNull();
      $timeout.flush(1);
      expect(TestManager._poll).toHaveBeenCalled();
    });
  });

  describe("_poll", function() {
    it("calls reloadItems", function() {
      var defer = $q.defer();
      spyOn(TestManager, "reloadItems").and.returnValue(defer.promise);
      TestManager._poll();
      expect(TestManager.reloadItems).toHaveBeenCalled();
    });

    it("calls _pollAgain with timeout", function() {
      var defer = $q.defer();
      spyOn(TestManager, "_pollAgain");
      spyOn(TestManager, "reloadItems").and.returnValue(defer.promise);
      TestManager._poll();
      defer.resolve([{}]);
      $rootScope.$digest();
      expect(TestManager._pollAgain).toHaveBeenCalledWith(
        TestManager._pollTimeout
      );
    });

    it("calls _pollAgain with empty timeout", function() {
      var defer = $q.defer();
      spyOn(TestManager, "_pollAgain");
      spyOn(TestManager, "reloadItems").and.returnValue(defer.promise);
      TestManager._poll();
      defer.resolve([]);
      $rootScope.$digest();
      expect(TestManager._pollAgain).toHaveBeenCalledWith(
        TestManager._pollEmptyTimeout
      );
    });

    it("calls _pollAgain with error timeout", function() {
      var defer = $q.defer();
      spyOn(TestManager, "_pollAgain");
      spyOn(TestManager, "reloadItems").and.returnValue(defer.promise);
      TestManager._poll();
      defer.reject(makeName("error"));
      $rootScope.$digest();
      expect(TestManager._pollAgain).toHaveBeenCalledWith(
        TestManager._pollErrorTimeout
      );
    });
  });
});
