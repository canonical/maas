/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ManagerHelperService.
 */

describe("ManagerHelperService", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $rootScope, $scope, $timeout, $q;
  beforeEach(inject(function($injector) {
    $rootScope = $injector.get("$rootScope");
    $timeout = $injector.get("$timeout");
    $q = $injector.get("$q");
    $scope = $rootScope.$new();
  }));

  // Load the ManagerHelperService.
  var ManagerHelperService, RegionConnection;
  beforeEach(inject(function($injector) {
    ManagerHelperService = $injector.get("ManagerHelperService");
    RegionConnection = $injector.get("RegionConnection");
  }));

  // Makes a fake manager.
  function makeManager(type) {
    if (angular.isUndefined(type)) {
      type = "notify";
    }
    var manager = {
      _type: type,
      _scopes: [],
      isLoaded: jasmine.createSpy(),
      loadItems: jasmine.createSpy(),
      enableAutoReload: jasmine.createSpy(),
      isPolling: jasmine.createSpy(),
      startPolling: jasmine.createSpy(),
      stopPolling: jasmine.createSpy()
    };
    manager.isLoaded.and.returnValue(false);
    manager.loadItems.and.returnValue($q.defer().promise);
    return manager;
  }

  describe("loadManager - notify", function() {
    it("calls RegionConnection.defaultConnect", function() {
      spyOn(RegionConnection, "defaultConnect").and.returnValue(
        $q.defer().promise
      );
      var manager = makeManager("notify");
      ManagerHelperService.loadManager($scope, manager);
      expect(RegionConnection.defaultConnect).toHaveBeenCalled();
    });

    it("doesn't call loadItems if manager already loaded", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      manager.isLoaded.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.loadItems).not.toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("adds scope if manager already loaded", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      manager.isLoaded.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager._scopes).toEqual([$scope]);
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("calls loadItems if manager not loaded", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      var loadItemsDefer = $q.defer();
      manager.loadItems.and.returnValue(loadItemsDefer.promise);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.loadItems).toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $rootScope.$digest();
      loadItemsDefer.resolve();
      $rootScope.$digest();
    });

    it("adds scope once loadItems resolves", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      var loadItemsDefer = $q.defer();
      manager.loadItems.and.returnValue(loadItemsDefer.promise);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.loadItems).toHaveBeenCalled();
      });
      defer.resolve();
      $rootScope.$digest();

      loadItemsDefer.promise.then(function() {
        expect(manager._scopes).toEqual([$scope]);
        done();
      });
      loadItemsDefer.resolve();
      $rootScope.$digest();
    });

    it("calls enableAutoReload", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      manager.isLoaded.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.enableAutoReload).toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("on $destroy scope is removed from manager", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("notify");
      manager.isLoaded.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager);
      defer.resolve();
      $timeout.flush();

      expect(manager._scopes).toEqual([$scope]);
      $scope.$emit("$destroy");
      $scope.$digest();
      expect(manager._scopes).toEqual([]);
    });
  });

  describe("loadManager - poll", function() {
    it("calls RegionConnection.defaultConnect", function() {
      spyOn(RegionConnection, "defaultConnect").and.returnValue(
        $q.defer().promise
      );
      var manager = makeManager("poll");
      ManagerHelperService.loadManager($scope, manager);
      expect(RegionConnection.defaultConnect).toHaveBeenCalled();
    });

    it("doesn't call startPolling if already polling", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      manager.isPolling.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.startPolling).not.toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("adds scope if manager already loaded", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      manager.isPolling.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager._scopes).toEqual([$scope]);
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("calls startPolling if manager not polling", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      var startPollingDefer = $q.defer();
      manager.startPolling.and.returnValue(startPollingDefer.promise);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.startPolling).toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $rootScope.$digest();
      startPollingDefer.resolve();
      $rootScope.$digest();
    });

    it("adds scope once startPolling resolves", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      var startPollingDefer = $q.defer();
      manager.startPolling.and.returnValue(startPollingDefer.promise);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.startPolling).toHaveBeenCalled();
      });
      defer.resolve();
      $rootScope.$digest();

      startPollingDefer.promise.then(function() {
        expect(manager._scopes).toEqual([$scope]);
        done();
      });
      startPollingDefer.resolve();
      $rootScope.$digest();
    });

    it("doesn't call enableAutoReload", function(done) {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      manager.isPolling.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager).then(function() {
        expect(manager.enableAutoReload).not.toHaveBeenCalled();
        done();
      });
      defer.resolve();
      $timeout.flush();
    });

    it("on $destroy stopPolling is called", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      manager.isPolling.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager);
      defer.resolve();
      $timeout.flush();

      expect(manager._scopes).toEqual([$scope]);
      $scope.$emit("$destroy");
      $scope.$digest();
      expect(manager._scopes).toEqual([]);
      expect(manager.stopPolling).toHaveBeenCalled();
    });

    it("on $destroy stopPolling not called if loaded twice", function() {
      var defer = $q.defer();
      spyOn(RegionConnection, "defaultConnect").and.returnValue(defer.promise);
      var manager = makeManager("poll");
      manager.isPolling.and.returnValue(true);
      ManagerHelperService.loadManager($scope, manager);
      var $otherScope = $rootScope.$new();
      ManagerHelperService.loadManager($otherScope, manager);
      defer.resolve();
      $timeout.flush();

      expect(manager._scopes).toEqual([$scope, $otherScope]);
      $scope.$emit("$destroy");
      $scope.$digest();
      expect(manager._scopes).toEqual([$otherScope]);
      expect(manager.stopPolling).not.toHaveBeenCalled();
    });
  });

  describe("loadManagers", function() {
    it("calls loadManager for all managers", function(done) {
      var managers = [makeManager(), makeManager()];
      var defers = [$q.defer(), $q.defer()];
      var i = 0;
      spyOn(ManagerHelperService, "loadManager").and.callFake(function(
        scope,
        manager
      ) {
        expect(manager).toBe(managers[i]);
        return defers[i++].promise;
      });
      ManagerHelperService.loadManagers($scope, managers).then(function(
        loadedManagers
      ) {
        expect(loadedManagers).toBe(managers);
        done();
      });
      defers[0].resolve();
      $rootScope.$digest();
      defers[1].resolve();
      $rootScope.$digest();
    });
  });

  describe("tryParsingJSON", function() {
    // Note: we're putting a lot of trust in JSON.parse(), so one simple
    // test should be enough.
    it("converts a JSON string into a JSON object", function() {
      var result = ManagerHelperService.tryParsingJSON('{ "a": "b" }');
      expect(result).toEqual({ a: "b" });
    });

    it("converts a non-JSON string into a string", function() {
      var result = ManagerHelperService.tryParsingJSON("Not a JSON string.");
      expect(result).toEqual("Not a JSON string.");
    });
  });

  describe("getPrintableString", function() {
    it("converts a flat dictionary to a printable string", function() {
      var result = ManagerHelperService.getPrintableString(
        {
          a: "bc",
          d: 1
        },
        true
      );
      expect(result).toEqual("a: bc\nd: 1");
    });

    it("converts a dictionary of lists to a string with labels", function() {
      var result = ManagerHelperService.getPrintableString(
        {
          a: ["b", "cd"]
        },
        true
      );
      expect(result).toEqual("a: b  cd");
    });

    it("converts a dictionary of lists to a string without labels", function() {
      var result = ManagerHelperService.getPrintableString(
        {
          a: ["b", "c"]
        },
        false
      );
      expect(result).toEqual("b  c");
    });

    it(`converts multiple key dictionary to
        multi-line string with labels`, function() {
      var result = ManagerHelperService.getPrintableString(
        {
          a: ["b", "cx"],
          d: ["e", "f"]
        },
        true
      );
      expect(result).toEqual("a: b  cx\nd: e  f");
    });
  });

  describe("parseValidationError", function() {
    it("returns a flat error for a flat string", function() {
      var result = ManagerHelperService.parseValidationError(
        "This is an error."
      );
      expect(result).toEqual("This is an error.");
    });

    it("returns a formatted error for a JSON string without names", function() {
      var result = ManagerHelperService.parseValidationError(
        '{"This": "is an error on JSON."}',
        false
      );
      expect(result).toEqual("is an error on JSON.");
    });

    it("returns a formatted error for a JSON string with names", function() {
      var result = ManagerHelperService.parseValidationError(
        '{"This": "is an error on JSON."}',
        true
      );
      expect(result).toEqual("This: is an error on JSON.");
    });
  });
});
