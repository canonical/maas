/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ZonesListController.
 */

import MockWebSocket from "testing/websocket";

describe("ZonesListController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $scope, $q, $routeParams;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
    $routeParams = {};
  }));

  // Load the managers and services.
  var ZonesManager, UsersManager;
  var ManagerHelperService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    ZonesManager = $injector.get("ZonesManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Makes the ZonesListController
  function makeController(loadManagerDefer, defaultConnectDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("ZonesListController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      ZonesManager: ZonesManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Zones");
    expect($rootScope.page).toBe("zones");
  });

  it("sets initial values on $scope", function() {
    // tab-independent variables.
    makeController();
    expect($scope.zones).toBe(ZonesManager.getItems());
    expect($scope.loading).toBe(true);
  });

  it("calls loadManagers with [ZonesManager, UsersManager]", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ZonesManager,
      UsersManager
    ]);
  });

  it("sets loading to false when loadManagers resolves", function() {
    var defer = $q.defer();
    makeController(defer);
    defer.resolve();
    $rootScope.$digest();
    expect($scope.loading).toBe(false);
  });

  describe("addZone", function() {
    it("sets action.open to true", function() {
      makeController();
      $scope.addZone();
      expect($scope.action.open).toBe(true);
    });
  });

  describe("closeZone", function() {
    it("set action.open to false and clears action.obj", function() {
      makeController();
      var obj = {};
      $scope.action.obj = obj;
      $scope.action.open = true;
      $scope.closeZone();
      expect($scope.action.open).toBe(false);
      expect($scope.action.obj).toEqual({});
      expect($scope.action.obj).not.toBe(obj);
    });
  });
});
