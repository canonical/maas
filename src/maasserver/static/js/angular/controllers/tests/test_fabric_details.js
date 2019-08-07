/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for FabricsListController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("FabricDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make a fake fabric
  function makeFabric() {
    var fabric = {
      id: makeInteger(1, 10000),
      name: makeName("fabric")
    };
    FabricsManager._items.push(fabric);
    return fabric;
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
  var FabricsManager, VLANsManager, SubnetsManager, SpacesManager;
  var ControllersManager, UsersManager, ManagerHelperService, ErrorService;
  var RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    FabricsManager = $injector.get("FabricsManager");
    VLANsManager = $injector.get("VLANsManager");
    SubnetsManager = $injector.get("SubnetsManager");
    SpacesManager = $injector.get("SpacesManager");
    ControllersManager = $injector.get("ControllersManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var fabric;
  beforeEach(function() {
    fabric = makeFabric();
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
    var controller = $controller("FabricDetailsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $location: $location,
      FabricsManager: FabricsManager,
      VLANsManager: VLANsManager,
      SubnetsManager: SubnetsManager,
      SpacesManager: SpacesManager,
      ControllersManager: ControllersManager,
      UsersManager: UsersManager,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });
    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(FabricsManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    var defer = $q.defer();
    var controller = makeController(defer);
    $routeParams.fabric_id = fabric.id;

    $rootScope.$digest();
    defer.resolve();

    $rootScope.$digest();
    setActiveDefer.resolve(fabric);
    $rootScope.$digest();

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("networks");
  });

  it("raises error if fabric identifier is invalid", function() {
    spyOn(FabricsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ErrorService, "raiseError").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.fabric_id = "xyzzy";

    defer.resolve();
    $rootScope.$digest();

    expect($scope.fabric).toBe(null);
    expect($scope.loaded).toBe(false);
    expect(FabricsManager.setActiveItem).not.toHaveBeenCalled();
    expect(ErrorService.raiseError).toHaveBeenCalled();
  });

  it("doesn't call setActiveItem if fabric is loaded", function() {
    spyOn(FabricsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    FabricsManager._activeItem = fabric;
    $routeParams.fabric_id = fabric.id;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.fabric).toBe(fabric);
    expect($scope.loaded).toBe(true);
    expect(FabricsManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if fabric is not active", function() {
    spyOn(FabricsManager, "setActiveItem").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.fabric_id = fabric.id;

    defer.resolve();
    $rootScope.$digest();

    expect(FabricsManager.setActiveItem).toHaveBeenCalledWith(fabric.id);
  });

  it("sets fabric and loaded once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.fabric).toBe(fabric);
    expect($scope.loaded).toBe(true);
  });

  it("title is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(fabric.name);
  });

  it("default fabric title is not special", function() {
    fabric.id = 0;
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(fabric.name);
  });

  it("updates $scope.rows with VLANs containing subnet(s)", function() {
    var spaces = [{ id: 0, name: "space-0" }];
    var vlans = [{ id: 1, name: "vlan4", vid: 4, fabric: fabric.id }];
    var subnets = [
      { id: 0, name: "subnet1", vlan: 1, space: 0, cidr: "10.20.0.0/16" }
    ];
    fabric.vlan_ids = [1];
    fabric.default_vlan_id = 1;
    spaces[0].subnet_ids = [0];
    SpacesManager._items.push(spaces[0]);
    VLANsManager._items.push(vlans[0]);
    SubnetsManager._items.push(subnets[0]);
    makeControllerResolveSetActiveItem();
    $scope.$apply();
    $rootScope.$digest();
    var rows = $scope.rows;
    expect(rows[0].vlan).toBe(vlans[0]);
    expect(rows[0].subnet_name).toEqual("10.20.0.0/16 (subnet1)");
    expect(rows[0].space_name).toEqual("space-0");
  });

  it("updates $scope.rows with VLANs containing no subnet(s)", function() {
    var vlans = [{ id: 1, name: "vlan4", vid: 4, fabric: fabric.id }];
    fabric.vlan_ids = [1];
    fabric.default_vlan_id = 1;
    VLANsManager._items.push(vlans[0]);
    makeControllerResolveSetActiveItem();
    $rootScope.$digest();
    var rows = $scope.rows;
    expect(rows[0].vlan).toBe(vlans[0]);
    expect(rows[0].subnet_name).toBe(null);
    expect(rows[0].space_name).toBe(null);
  });

  describe("editSubnetSummary", function() {
    it("enters edit mode for summary", function() {
      makeController();
      $scope.editSummary = false;
      $scope.enterEditSummary();
      expect($scope.editSummary).toBe(true);
    });
  });

  describe("exitEditSubnetSummary", function() {
    it("enters edit mode for summary", function() {
      makeController();
      $scope.editSummary = true;
      $scope.exitEditSummary();
      expect($scope.editSummary).toBe(false);
    });
  });

  describe("canBeDeleted", function() {
    it("returns false if fabric is null", function() {
      makeControllerResolveSetActiveItem();
      $scope.fabric = null;
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns false if fabric is default fabric", function() {
      makeControllerResolveSetActiveItem();
      $scope.fabric.id = 0;
      expect($scope.canBeDeleted()).toBe(false);
    });

    it("returns true if fabric is not default fabric", function() {
      makeControllerResolveSetActiveItem();
      $scope.fabric.id = 1;
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

  describe("deleteFabric", function() {
    it("calls deleteFabric", function() {
      $location = {};
      $location.path = jasmine.createSpy("path");
      $location.search = jasmine.createSpy("search");
      makeController();
      var deleteFabric = spyOn(FabricsManager, "deleteFabric");
      var defer = $q.defer();
      deleteFabric.and.returnValue(defer.promise);
      $scope.deleteConfirmButton();
      defer.resolve();
      $rootScope.$apply();
      expect(deleteFabric).toHaveBeenCalled();
      expect($location.path).toHaveBeenCalledWith("/networks");
      expect($location.search).toHaveBeenCalledWith("by", "fabric");
    });
  });
});
