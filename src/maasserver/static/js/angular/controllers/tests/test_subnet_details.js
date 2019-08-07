/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubnetsListController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("SubnetDetailsController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Make a fake fabric
  function makeFabric() {
    var fabric = {
      id: 0,
      name: "fabric-0"
    };
    FabricsManager._items.push(fabric);
  }

  function makeVLAN() {
    var vlan = {
      id: 0,
      fabric: 0,
      vid: 0
    };
    VLANsManager._items.push(vlan);
  }

  function makeSpace() {
    var space = {
      id: 0,
      name: "default"
    };
    SpacesManager._items.push(space);
  }

  // Make a fake subnet
  function makeSubnet() {
    var subnet = {
      id: makeInteger(1, 10000),
      cidr: "169.254.0.0/24",
      name: "Link Local",
      vlan: 0,
      dns_servers: []
    };
    SubnetsManager._items.push(subnet);
    return subnet;
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
    $location = $injector.get("$filter");
  }));

  // Load any injected managers and services.
  var ConfigsManager, SubnetsManager, IPRangesManager, StaticRoutesManager;
  var SpacesManager, VLANsManager, FabricsManager;
  var ErrorService, ConverterService, ManagerHelperService;
  var RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    ConfigsManager = $injector.get("ConfigsManager");
    SubnetsManager = $injector.get("SubnetsManager");
    IPRangesManager = $injector.get("IPRangesManager");
    StaticRoutesManager = $injector.get("StaticRoutesManager");
    SpacesManager = $injector.get("SpacesManager");
    VLANsManager = $injector.get("VLANsManager");
    FabricsManager = $injector.get("FabricsManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    ErrorService = $injector.get("ErrorService");
    ConverterService = $injector.get("ConverterService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  var subnet;
  beforeEach(function() {
    makeFabric();
    makeVLAN();
    makeSpace();
    subnet = makeSubnet();
  });

  // Makes the SubnetDetailsController
  function makeController(loadManagersDefer) {
    var loadManagers = spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagersDefer)) {
      loadManagers.and.returnValue(loadManagersDefer.promise);
    } else {
      loadManagers.and.returnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("SubnetDetailsController", {
      $scope: $scope,
      $rootScope: $rootScope,
      $routeParams: $routeParams,
      $location: $location,
      ConfigsManager: ConfigsManager,
      SubnetsManager: SubnetsManager,
      IPRangesManager: IPRangesManager,
      SpacesManager: SpacesManager,
      VLANsManager: VLANsManager,
      FabricsManager: FabricsManager,
      ManagerHelperService: ManagerHelperService,
      ErrorService: ErrorService
    });

    return controller;
  }

  // Make the controller and resolve the setActiveItem call.
  function makeControllerResolveSetActiveItem() {
    var setActiveDefer = $q.defer();
    spyOn(SubnetsManager, "setActiveItem").and.returnValue(
      setActiveDefer.promise
    );
    spyOn(ConfigsManager, "getItemFromList").and.returnValue({
      value: "",
      choices: []
    });
    var defer = $q.defer();
    var controller = makeController(defer);
    $routeParams.subnet_id = subnet.id;

    defer.resolve();
    $rootScope.$digest();
    setActiveDefer.resolve(subnet);
    $rootScope.$digest();

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Loading...");
    expect($rootScope.page).toBe("networks");
  });

  it("raises error if subnet identifier is invalid", function() {
    spyOn(SubnetsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ConfigsManager, "getItemFromList").and.returnValue({
      value: "",
      choices: []
    });
    spyOn(ErrorService, "raiseError").and.returnValue($q.defer().promise);
    var defer = $q.defer();
    makeController(defer);
    $routeParams.subnet_id = "xyzzy";

    defer.resolve();
    $rootScope.$digest();

    expect($scope.subnet).toBe(null);
    expect($scope.loaded).toBe(false);
    expect(SubnetsManager.setActiveItem).not.toHaveBeenCalled();
    expect(ErrorService.raiseError).toHaveBeenCalled();
  });

  it("doesn't call setActiveItem if subnet is loaded", function() {
    spyOn(SubnetsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ConfigsManager, "getItemFromList").and.returnValue({
      value: "",
      choices: []
    });
    var defer = $q.defer();
    makeController(defer);
    SubnetsManager._activeItem = subnet;
    $routeParams.subnet_id = subnet.id;

    defer.resolve();
    $rootScope.$digest();

    expect($scope.subnet).toBe(subnet);
    expect($scope.loaded).toBe(true);
    expect(SubnetsManager.setActiveItem).not.toHaveBeenCalled();
  });

  it("calls setActiveItem if subnet is not active", function() {
    spyOn(SubnetsManager, "setActiveItem").and.returnValue($q.defer().promise);
    spyOn(ConfigsManager, "getItemFromList").and.returnValue({
      value: "",
      choices: []
    });
    var defer = $q.defer();
    makeController(defer);
    $routeParams.subnet_id = subnet.id;

    defer.resolve();
    $rootScope.$digest();

    expect(SubnetsManager.setActiveItem).toHaveBeenCalledWith(subnet.id);
  });

  it("sets subnet and loaded once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($scope.subnet).toBe(subnet);
    expect($scope.loaded).toBe(true);
  });

  it("title is updated once setActiveItem resolves", function() {
    makeControllerResolveSetActiveItem();
    expect($rootScope.title).toBe(subnet.cidr + " (" + subnet.name + ")");
  });

  describe("ipSort", function() {
    it("calls ipv4ToInteger when ipVersion == 4", function() {
      makeControllerResolveSetActiveItem();
      $scope.ipVersion = 4;
      var expected = {};
      spyOn(ConverterService, "ipv4ToInteger").and.returnValue(expected);
      var ipAddress = {
        ip: {}
      };
      var observed = $scope.ipSort(ipAddress);
      expect(ConverterService.ipv4ToInteger).toHaveBeenCalledWith(ipAddress.ip);
      expect(observed).toBe(expected);
    });

    it("calls ipv6Expand when ipVersion == 6", function() {
      makeControllerResolveSetActiveItem();
      $scope.ipVersion = 6;
      var expected = {};
      spyOn(ConverterService, "ipv6Expand").and.returnValue(expected);
      var ipAddress = {
        ip: {}
      };
      var observed = $scope.ipSort(ipAddress);
      expect(ConverterService.ipv6Expand).toHaveBeenCalledWith(ipAddress.ip);
      expect(observed).toBe(expected);
    });

    it("is predicate default", function() {
      makeControllerResolveSetActiveItem();
      expect($scope.predicate).toBe($scope.ipSort);
    });
  });

  describe("getAllocType", function() {
    var scenarios = {
      0: "Automatic",
      1: "Static",
      4: "User reserved",
      5: "DHCP",
      6: "Observed",
      7: "Unknown"
    };

    angular.forEach(scenarios, function(expected, allocType) {
      it("allocType( " + allocType + ") = " + expected, function() {
        makeControllerResolveSetActiveItem();
        expect($scope.getAllocType(allocType)).toBe(expected);
      });
    });
  });

  describe("allocTypeSort", function() {
    it("calls getAllocType", function() {
      makeControllerResolveSetActiveItem();
      var expected = {};
      spyOn($scope, "getAllocType").and.returnValue(expected);
      var ipAddress = {
        alloc_type: {}
      };
      var observed = $scope.allocTypeSort(ipAddress);
      expect($scope.getAllocType).toHaveBeenCalledWith(ipAddress.alloc_type);
      expect(observed).toBe(expected);
    });
  });

  describe("getUsageForIP", function() {
    var scenarios = {
      0: "Machine",
      1: "Device",
      2: "Rack controller",
      3: "Region controller",
      4: "Rack and region controller",
      5: "Chassis",
      6: "Storage",
      7: "Unknown"
    };

    angular.forEach(scenarios, function(expected, nodeType) {
      it("nodeType( " + nodeType + ") = " + expected, function() {
        makeControllerResolveSetActiveItem();
        var ip = {};
        ip.node_summary = {};
        ip.node_summary.node_type = nodeType;
        expect($scope.getUsageForIP(ip)).toBe(expected);
      });
    });

    it("handles BMCs", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {
        bmcs: []
      };
      expect($scope.getUsageForIP(ipAddress)).toBe("BMC");
    });

    it("handles containers", function() {
      makeControllerResolveSetActiveItem();
      var ip = {};
      ip.node_summary = {};
      ip.node_summary.node_type = 1;
      ip.node_summary.is_container = true;
      expect($scope.getUsageForIP(ip)).toBe("Container");
    });

    it("handles DNS records", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {
        dns_records: []
      };
      expect($scope.getUsageForIP(ipAddress)).toBe("DNS");
    });

    it("handles the unknown", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {};
      expect($scope.getUsageForIP(ipAddress)).toBe("Unknown");
    });
  });

  describe("nodeTypeSort", function() {
    it("calls getUsageForIP", function() {
      makeControllerResolveSetActiveItem();
      var expected = {};
      spyOn($scope, "getUsageForIP").and.returnValue(expected);
      var ipAddress = {
        node_summary: {
          node_type: {}
        }
      };
      var observed = $scope.nodeTypeSort(ipAddress);
      expect($scope.getUsageForIP).toHaveBeenCalledWith(ipAddress);
      expect(observed).toBe(expected);
    });
  });

  describe("ownerSort", function() {
    it("returns owner", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {
        user: makeName("owner")
      };
      var observed = $scope.ownerSort(ipAddress);
      expect(observed).toBe(ipAddress.user);
    });

    it("returns MAAS for empty string", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {
        user: ""
      };
      var observed = $scope.ownerSort(ipAddress);
      expect(observed).toBe("MAAS");
    });

    it("returns MAAS for null", function() {
      makeControllerResolveSetActiveItem();
      var ipAddress = {
        user: null
      };
      var observed = $scope.ownerSort(ipAddress);
      expect(observed).toBe("MAAS");
    });
  });

  describe("sortIPTable", function() {
    it("sets predicate and inverts reverse", function() {
      makeControllerResolveSetActiveItem();
      $scope.reverse = true;
      var predicate = {};
      $scope.sortIPTable(predicate);
      expect($scope.predicate).toBe(predicate);
      expect($scope.reverse).toBe(false);
      $scope.sortIPTable(predicate);
      expect($scope.reverse).toBe(true);
    });
  });

  describe("subnetPreSave", function() {
    it("updates vlan when fabric changed", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var fabric = {
        id: makeInteger(1, 100),
        default_vlan_id: vlan.id,
        vlan_ids: [vlan.id]
      };
      FabricsManager._items.push(fabric);
      var subnet = {
        fabric: fabric.id
      };
      var updatedSubnet = $scope.subnetPreSave(subnet, ["fabric"]);
      expect(updatedSubnet.vlan).toBe(vlan.id);
    });
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

  describe("addStaticRoute", function() {
    it("set newStaticRoute", function() {
      makeController();
      $scope.subnet = {
        id: makeInteger(0, 100)
      };
      $scope.addStaticRoute();
      expect($scope.newStaticRoute).toEqual({
        source: $scope.subnet.id,
        gateway_ip: "",
        destination: null,
        metric: 0
      });
    });

    it("clear editStaticRoute", function() {
      makeController();
      $scope.subnet = {
        id: makeInteger(0, 100)
      };
      $scope.editStaticRoute = {};
      $scope.addStaticRoute();
      expect($scope.editStaticRoute).toBeNull();
    });

    it("clear deleteStaticRoute", function() {
      makeController();
      $scope.subnet = {
        id: makeInteger(0, 100)
      };
      $scope.deleteStaticRoute = {};
      $scope.addStaticRoute();
      expect($scope.deleteStaticRoute).toBeNull();
    });
  });

  describe("cancelAddStaticRoute", function() {
    it("clears newStaticRoute", function() {
      makeController();
      $scope.newStaticRoute = {};
      $scope.cancelAddStaticRoute();
      expect($scope.newStaticRoute).toBeNull();
    });
  });

  describe("isStaticRouteInEditMode", function() {
    it("returns true when editStaticRoute", function() {
      makeController();
      var route = {};
      $scope.editStaticRoute = route;
      expect($scope.isStaticRouteInEditMode(route)).toBe(true);
    });

    it("returns false when editIPRange", function() {
      makeController();
      var route = {};
      $scope.editStaticRoute = route;
      expect($scope.isStaticRouteInEditMode({})).toBe(false);
    });
  });

  describe("staticRouteToggleEditMode", function() {
    it("clears newStaticRoute", function() {
      makeController();
      $scope.newStaticRoute = {};
      $scope.staticRouteToggleEditMode({});
      expect($scope.newStaticRoute).toBeNull();
    });

    it("clears deleteStaticRoute", function() {
      makeController();
      $scope.deleteStaticRoute = {};
      $scope.staticRouteToggleEditMode({});
      expect($scope.deleteStaticRoute).toBeNull();
    });

    it("clears editStaticRoute when already set", function() {
      makeController();
      var route = {};
      $scope.editStaticRoute = route;
      $scope.staticRouteToggleEditMode(route);
      expect($scope.editStaticRoute).toBeNull();
    });

    it("sets editStaticRoute when different range", function() {
      makeController();
      var route = {};
      var otherRoute = {};
      $scope.editStaticRoute = otherRoute;
      $scope.staticRouteToggleEditMode(route);
      expect($scope.editStaticRoute).toBe(route);
    });
  });

  describe("isStaticRouteInDeleteMode", function() {
    it("return true when deleteStaticRoute is same", function() {
      makeController();
      var route = {};
      $scope.deleteStaticRoute = route;
      expect($scope.isStaticRouteInDeleteMode(route)).toBe(true);
    });

    it("return false when deleteIPRange is different", function() {
      makeController();
      var route = {};
      $scope.deleteStaticRoute = route;
      expect($scope.isStaticRouteInDeleteMode({})).toBe(false);
    });
  });

  describe("staticRouteEnterDeleteMode", function() {
    it("clears edit and new and sets deleteStaticRoute", function() {
      makeController();
      var route = {};
      $scope.newStaticRoute = {};
      $scope.editStaticRoute = {};
      $scope.staticRouteEnterDeleteMode(route);
      expect($scope.newStaticRoute).toBeNull();
      expect($scope.editStaticRoute).toBeNull();
      expect($scope.deleteStaticRoute).toBe(route);
    });
  });

  describe("staticRouteCancelDelete", function() {
    it("clears deleteStaticRoute", function() {
      makeController();
      $scope.deleteStaticRoute = {};
      $scope.staticRouteCancelDelete();
      expect($scope.deleteStaticRoute).toBeNull();
    });
  });

  describe("staticRouteConfirmDelete", function() {
    it("calls deleteItem and clears deleteStaticRoute on resolve", function() {
      makeController();
      var route = {};
      $scope.deleteStaticRoute = route;

      var defer = $q.defer();
      spyOn(StaticRoutesManager, "deleteItem").and.returnValue(defer.promise);
      $scope.staticRouteConfirmDelete();

      expect(StaticRoutesManager.deleteItem).toHaveBeenCalledWith(route);
      defer.resolve();
      $scope.$digest();

      expect($scope.deleteStaticRoute).toBeNull();
    });
  });

  describe("actionRetry", function() {
    it("clears actionError", function() {
      makeController();
      $scope.actionError = {};
      $scope.actionRetry();
      expect($scope.actionError).toBeNull();
    });
  });

  describe("actionGo", function() {
    it("map_subnet action calls scanSubnet", function() {
      makeControllerResolveSetActiveItem();
      var scanSubnet = spyOn(SubnetsManager, "scanSubnet");
      var defer = $q.defer();
      const result = {
        result: "Error message from scan.",
        scan_started_on: ["not empty"]
      };
      scanSubnet.and.returnValue(defer.promise);
      $scope.actionOption = {
        name: "map_subnet",
        title: "Map subnet"
      };
      $scope.actionGo();
      defer.resolve(result);
      $scope.$digest();
      expect(scanSubnet).toHaveBeenCalled();
      expect($scope.actionOption).toBeNull();
      expect($scope.actionError).toBeNull();
    });

    it("actionError populated on scans not started", function() {
      makeControllerResolveSetActiveItem();
      var scanSubnet = spyOn(SubnetsManager, "scanSubnet");
      var defer = $q.defer();
      const result = {
        result: "Error message from scan.",
        scan_started_on: []
      };
      scanSubnet.and.returnValue(defer.promise);
      $scope.actionOption = {
        name: "map_subnet",
        title: "Map subnet"
      };
      $scope.actionGo();
      defer.resolve(result);
      $scope.$digest();
      expect(scanSubnet).toHaveBeenCalled();
      expect($scope.actionError).toBe("Error message from scan.");
    });

    it("actionError populated on map_subnet action failure", function() {
      makeControllerResolveSetActiveItem();
      $scope.actionOption = {
        name: "map_subnet",
        title: "Map subnet"
      };
      var defer = $q.defer();
      spyOn(SubnetsManager, "scanSubnet").and.returnValue(defer.promise);
      $scope.actionGo();
      const error = "errorString";
      $scope.actionOption = null;
      defer.reject(error);
      $scope.$digest();
      expect($scope.actionError).toBe(error);
    });

    it("delete action calls deleteSubnet", function() {
      $location.path = jasmine.createSpy("path");
      makeControllerResolveSetActiveItem();
      var deleteSubnet = spyOn(SubnetsManager, "deleteSubnet");
      var defer = $q.defer();
      deleteSubnet.and.returnValue(defer.promise);
      $scope.actionOption = {
        name: "delete",
        title: "Delete"
      };
      $scope.actionGo();
      defer.resolve();
      $scope.$digest();
      expect(deleteSubnet).toHaveBeenCalled();
      expect($location.path).toHaveBeenCalledWith("/networks");
      expect($scope.actionOption).toBeNull();
      expect($scope.actionError).toBeNull();
    });

    it("actionError populated on delete action failure", function() {
      makeControllerResolveSetActiveItem();
      $scope.actionOption = {
        name: "delete",
        title: "Delete"
      };
      var defer = $q.defer();
      spyOn(SubnetsManager, "deleteSubnet").and.returnValue(defer.promise);
      $scope.actionGo();
      const error = "errorString";
      $scope.actionOption = null;
      defer.reject(error);
      $scope.$digest();
      expect($scope.actionError).toBe(error);
    });
  });

  describe("actionChanged", function() {
    it("clears actionError", function() {
      makeController();
      $scope.actionError = {};
      $scope.actionChanged();
      expect($scope.actionError).toBeNull();
    });
  });

  describe("cancelAction", function() {
    it("clears actionOption and actionError", function() {
      makeController();
      $scope.actionOption = {};
      $scope.actionError = {};
      $scope.cancelAction();
      expect($scope.actionOption).toBeNull();
      expect($scope.actionError).toBeNull();
    });
  });

  describe("DHCPEnabled", function() {
    it("returns undefined if no arguments provided", function() {
      makeController();
      expect($scope.DHCPEnabled()).toBeUndefined();
    });

    it("returns undefined if no subnet provided", function() {
      makeController();
      expect($scope.DHCPEnabled(null, [])).toBeUndefined();
    });

    it("returns undefined if subnet is not an object", function() {
      makeController();
      expect($scope.DHCPEnabled("foo", [])).toBeUndefined();
    });

    it("returns undefined if no vlans are provided", function() {
      makeController();
      expect($scope.DHCPEnabled({}, null)).toBeUndefined();
    });

    it("returns undefined if vlan is not an array", function() {
      makeController();
      expect($scope.DHCPEnabled({}, "foo")).toBeUndefined();
    });

    it("returns true if DHCP enabled on VLAN", function() {
      makeController();
      var subnet = { vlan: 5001 };
      var vlans = [{ id: 5001, dhcp_on: true }];
      expect($scope.DHCPEnabled(subnet, vlans)).toBe(true);
    });

    it("returns false if DHCP is not enabled on VLAN", function() {
      makeController();
      var subnet = { vlan: 5001 };
      var vlans = [{ id: 5001, dhcp_on: false }];
      expect($scope.DHCPEnabled(subnet, vlans)).toBe(false);
    });
  });

  describe("getVLANOnSubnet", function() {
    it("returns vlan from subnet", function() {
      makeController();
      var subnet = { vlan: 5001 };
      var vlans = [{ id: 5001 }, { id: 5002 }];
      expect($scope.getVLANOnSubnet(subnet, vlans)).toEqual(vlans[0]);
    });

    it("returns undefined if no vlan", function() {
      makeController();
      var subnet = { vlan: 5001 };
      var vlans = [{ id: 5002 }];
      expect($scope.getVLANOnSubnet(subnet, vlans)).toBeUndefined();
    });
  });

  describe("hasIPAddresses", function() {
    it("returns undefined if no argument provided", function() {
      makeController();
      expect($scope.hasIPAddresses()).toBeUndefined();
    });

    it("returns undefined if argument is not an array", function() {
      makeController();
      expect($scope.hasIPAddresses("foo")).toBeUndefined();
    });

    it("returns true if argument has IP addresses", function() {
      makeController();
      var IPAddresses = [{ ip: "172.16.4.14" }];
      expect($scope.hasIPAddresses(IPAddresses)).toBe(true);
    });

    it("returns false if argument has no IP addresses", function() {
      makeController();
      expect($scope.hasIPAddresses([])).toBe(false);
    });
  });
});
