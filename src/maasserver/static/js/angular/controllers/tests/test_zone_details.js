/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ZonesListController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("ZoneDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make a fake zone
  function makeZone() {
    var zone = {
      id: makeInteger(1, 10000),
      name: makeName("zone")
    };
    ZonesManager._items.push(zone);
    return zone;
  }

  // Grab the needed angular pieces.
  var $controller, $rootScope, $location, $scope, $q, $routeParams;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $routeParams = {};
  }));

  // Load any injected managers and services.
  var ZonesManager, UsersManager, ManagerHelperService, ErrorService;
  var RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    ZonesManager = $injector.get("ZonesManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var zone;
  beforeEach(function() {
    zone = makeZone();
  });

  // Makes the NodesListController
  function makeController(loadManagerDefer) {
    spyOn(UsersManager, "isSuperUser").and.returnValue(true);
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("ZoneDetailsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $location: $location,
      ZonesManager: ZonesManager,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });

    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(ZonesManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    var controller = makeController(defer);
    $routeParams.zone_id = zone.id;

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(zone);
    $rootScope.$digest();

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("zones");
  });

  it("raises error if zone identifier is invalid", function() {
    spyOn(ZonesManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ErrorService, "raiseError").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.zone_id = "xyzzy";

    defer.resolve();
    $rootScope.$digest();

    expect($scope.zone).toBe(null);
    expect($scope.loaded).toBe(false);
    expect(ZonesManager.setActiveItem).not.toHaveBeenCalled();
    expect(ErrorService.raiseError).toHaveBeenCalled();
  });

  it("doesn't call setActiveItem if zone is loaded", function() {
    spyOn(ZonesManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    ZonesManager._activeItem = zone;
    $routeParams.zone_id = zone.id;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.zone).toBe(zone);
    expect($scope.loaded).toBe(true);
    expect(ZonesManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if zone is not active", function() {
    spyOn(ZonesManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.zone_id = zone.id;

    defer.resolve();
    $rootScope.$digest();

    expect(ZonesManager.setActiveItem).toHaveBeenCalledWith(zone.id);
  });

  it("sets zone and loaded once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.zone).toBe(zone);
    expect($scope.loaded).toBe(true);
  });

  it("title is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(zone.name);
  });

  describe("canBeDeleted", function() {
    it("returns false if zone is null", function() {
      makeControllerResolveSetActiveItem();
      $scope.zone = null;
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns false if zone id is 0", function() {
      makeControllerResolveSetActiveItem();
      $scope.zone.id = 0;
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns true if zone id > 0", function() {
      makeControllerResolveSetActiveItem();
      $scope.zone.id = 1;
      expect($scope.canBeDeleted()).toBe(true);
    });
  });

  describe("deleteButton", function() {
    it("confirms delete", function() {
      makeControllerResolveSetActiveItem();
      $scope.deleteButton();
      expect($scope.confirmingDelete).toBe(true);
    });

    it("clears error", function() {
      makeControllerResolveSetActiveItem();
      $scope.error = makeName("error");
      $scope.deleteButton();
      expect($scope.error).toBeNull();
    });
  });

  describe("cancelDeleteButton", function() {
    it("cancels delete", function() {
      makeControllerResolveSetActiveItem();
      $scope.deleteButton();
      $scope.cancelDeleteButton();
      expect($scope.confirmingDelete).toBe(false);
    });
  });

  describe("deleteZone", function() {
    it("calls deleteItem", function() {
      makeController();
      var deleteItem = spyOn(ZonesManager, "deleteItem");
      var defer = $q.defer();
      deleteItem.and.returnValue(defer.promise);
      $scope.deleteConfirmButton();
      expect(deleteItem).toHaveBeenCalled();
    });
  });
});
