/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DomainsListController.
 */

import { makeInteger } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("DomainsListController", function() {
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
  var DomainsManager, UsersManager;
  var ManagerHelperService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    DomainsManager = $injector.get("DomainsManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Makes the DomainsListController
  function makeController(loadManagerDefer, defaultConnectDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("DomainsListController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      DomainsManager: DomainsManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("DNS");
    expect($rootScope.page).toBe("domains");
  });

  it("sets initial values on $scope", function() {
    // tab-independent variables.
    makeController();
    expect($scope.domains).toBe(DomainsManager.getItems());
    expect($scope.loading).toBe(true);
  });

  it("calls loadManagers with [DomainsManager, UsersManager]", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      DomainsManager,
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

  describe("addDomain", function() {
    it("calls show in addDomainScope", function() {
      makeController();
      $scope.addDomainScope = {
        show: jasmine.createSpy("show")
      };
      $scope.addDomain();
      expect($scope.addDomainScope.show).toHaveBeenCalled();
    });
  });

  describe("cancelAddDomain", function() {
    it("calls cancel in addDomainScope", function() {
      makeController();
      $scope.addDomainScope = {
        cancel: jasmine.createSpy("cancel")
      };
      $scope.cancelAddDomain();
      expect($scope.addDomainScope.cancel).toHaveBeenCalled();
    });
  });

  describe("confirmSetDefault", function() {
    it("sets confirmSetDefaultRow to the specified row", function() {
      makeController();
      var obj = {
        id: makeInteger(0, 100)
      };
      $scope.confirmSetDefault(obj);
      expect($scope.confirmSetDefaultRow).toBe(obj);
    });
  });

  describe("cancelSetDefault", function() {
    it("sets confirmSetDefaultRow to the specified row", function() {
      makeController();
      var obj = {
        id: makeInteger(0, 100)
      };
      $scope.confirmSetDefaultRow = obj;
      $scope.cancelSetDefault();
      expect($scope.confirmSetDefaultRow).toBe(null);
    });
  });

  describe("setDefault", function() {
    it("calls DomainsManager.setDefault and clears selection", function() {
      makeController();
      spyOn(DomainsManager, "setDefault");
      var obj = {
        id: makeInteger(0, 100)
      };
      $scope.confirmSetDefaultRow = obj;
      $scope.setDefault(obj);
      expect(DomainsManager.setDefault).toHaveBeenCalledWith(obj);
      expect($scope.confirmSetDefaultRow).toBe(null);
    });
  });
});
