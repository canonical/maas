/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for BootResourcesManager.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("BootResourcesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $rootScope, $timeout, $q;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $timeout = $injector.get("$timeout");
    $q = $injector.get("$q");
  }));

  // Load the needed services.
  var BootResourcesManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    BootResourcesManager = $injector.get("BootResourcesManager");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  it("sets initial values", function() {
    expect(BootResourcesManager._loaded).toBe(false);
    expect(BootResourcesManager._data).toEqual({});
    expect(BootResourcesManager._polling).toBe(false);
    expect(BootResourcesManager._nextPromise).toBeNull();
    expect(BootResourcesManager._pollTimeout).toBe(10000);
    expect(BootResourcesManager._pollErrorTimeout).toBe(500);
    expect(BootResourcesManager._pollEmptyTimeout).toBe(3000);
  });

  describe("getData", function() {
    it("returns _data", function() {
      expect(BootResourcesManager.getData()).toBe(BootResourcesManager._data);
    });
  });

  describe("isLoaded", function() {
    it("returns _loaded", function() {
      var sentinel = {};
      BootResourcesManager._loaded = sentinel;
      expect(BootResourcesManager.isLoaded()).toBe(sentinel);
    });
  });

  describe("isPolling", function() {
    it("returns _polling", function() {
      var sentinel = {};
      BootResourcesManager._polling = sentinel;
      expect(BootResourcesManager.isPolling()).toBe(sentinel);
    });
  });

  describe("startPolling", function() {
    it("calls _poll and sets polling", function() {
      var sentinel = {};
      spyOn(BootResourcesManager, "_poll").and.returnValue(sentinel);
      expect(BootResourcesManager.startPolling()).toBe(sentinel);
      expect(BootResourcesManager._polling).toBe(true);
    });

    it("returns _nextPromise if already polling", function() {
      var sentinel = {};
      BootResourcesManager._polling = true;
      BootResourcesManager._nextPromise = sentinel;
      spyOn(BootResourcesManager, "_poll");
      expect(BootResourcesManager.startPolling()).toBe(sentinel);
      expect(BootResourcesManager._poll).not.toHaveBeenCalled();
    });
  });

  describe("stopPolling", function() {
    it("clears _polling and cancels _nextPromise", function() {
      var sentinel = {};
      BootResourcesManager._polling = true;
      BootResourcesManager._nextPromise = sentinel;
      spyOn($timeout, "cancel");
      BootResourcesManager.stopPolling();
      expect($timeout.cancel).toHaveBeenCalledWith(sentinel);
      expect(BootResourcesManager._nextPromise).toBeNull();
      expect(BootResourcesManager._polling).toBe(false);
    });
  });

  describe("_loadData", function() {
    it("calls bootresource.poll and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      BootResourcesManager._loadData().then(function(passedData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(passedData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.poll"
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });

  describe("stopImport", function() {
    it("calls bootresource.stop_import and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      var sentinel = {};
      BootResourcesManager.stopImport(sentinel).then(function(pData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(pData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.stop_import",
        sentinel
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });

  describe("saveUbuntu", function() {
    it("calls bootresource.save_ubuntu and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      var sentinel = {};
      BootResourcesManager.saveUbuntu(sentinel).then(function(pData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(pData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.save_ubuntu",
        sentinel
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });

  describe("saveUbuntuCore", function() {
    it("calls bootresource.save_ubuntu_core and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      var sentinel = {};
      BootResourcesManager.saveUbuntuCore(sentinel).then(function(pData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(pData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.save_ubuntu_core",
        sentinel
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });

  describe("saveOther", function() {
    it("calls bootresource.save_other and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      var sentinel = {};
      BootResourcesManager.saveOther(sentinel).then(function(pData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(pData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.save_other",
        sentinel
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });

  describe("fetch", function() {
    it("calls bootresource.fetch", function() {
      var returnSentinel = {};
      var sourceSentinel = {};
      spyOn(RegionConnection, "callMethod").and.returnValue(returnSentinel);
      expect(BootResourcesManager.fetch(sourceSentinel)).toBe(returnSentinel);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.fetch",
        sourceSentinel
      );
    });
  });

  describe("deleteImage", function() {
    it("calls bootresource.delete_image and sets _data", function(done) {
      var data = BootResourcesManager._data;
      var defer = $q.defer();
      spyOn(RegionConnection, "callMethod").and.returnValue(defer.promise);

      var newData = {
        key: makeName("value")
      };
      var sentinel = {};
      BootResourcesManager.deleteImage(sentinel).then(function(pData) {
        expect(BootResourcesManager._loaded).toBe(true);
        expect(BootResourcesManager._data).toBe(data);
        expect(BootResourcesManager._data).toBe(pData);
        expect(BootResourcesManager._data).toEqual(newData);
        done();
      });

      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "bootresource.delete_image",
        sentinel
      );
      defer.resolve(angular.toJson(newData));
      $rootScope.$digest();
    });
  });
});
