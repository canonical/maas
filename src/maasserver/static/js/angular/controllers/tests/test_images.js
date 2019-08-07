/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ImagesController.
 */

import MockWebSocket from "testing/websocket";

describe("ImagesController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
  }));

  // Load any injected managers and services.
  var BootResourcesManager, ConfigsManager, UsersManager;
  var ManagerHelperService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    BootResourcesManager = $injector.get("BootResourcesManager");
    ConfigsManager = $injector.get("ConfigsManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Makes the NodesListController
  function makeController(loadManagerDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.and.returnValue(loadManagerDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("ImagesController", {
      $scope: $scope,
      $rootScope: $rootScope,
      BootResourcesManager: BootResourcesManager,
      ConfigsManager: ConfigsManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("images");
  });

  it("calls loadManagers with correct managers", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      ConfigsManager,
      UsersManager
    ]);
  });

  it("sets initial $scope", function() {
    makeController();
    expect($scope.loading).toBe(true);
    expect($scope.bootResources).toBe(BootResourcesManager.getData());
    expect($scope.configManager).toBe(ConfigsManager);
    expect($scope.autoImport).toBeNull();
  });

  it("clears loading and sets title", function() {
    makeController();
    BootResourcesManager._data.resources = [];
    $scope.$digest();
    expect($scope.loading).toBe(false);
    expect($scope.title).toBe("Images");
  });

  it("sets autoImport object", function() {
    var defer = $q.defer();
    makeController(defer);
    var autoImport = {
      name: "boot_images_auto_import",
      value: true
    };
    ConfigsManager._items = [autoImport];
    defer.resolve();
    $scope.$digest();
    expect($scope.autoImport).toBe(autoImport);
  });

  describe("isSuperUser", function() {
    it("returns isSuperUser from UsersManager", function() {
      makeController();
      var sentinel = {};
      spyOn(UsersManager, "isSuperUser").and.returnValue(sentinel);
      expect($scope.isSuperUser()).toBe(sentinel);
    });
  });
});
