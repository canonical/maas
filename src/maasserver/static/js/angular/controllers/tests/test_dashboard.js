/* Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DashboardController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("DashboardController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $scope, $q, $location;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $location = $injector.get("$location");
    $scope = $rootScope.$new();
    $q = $injector.get("$q");
  }));

  // Load any injected managers and services.
  var DiscoveriesManager, DomainsManager, MachinesManager, DevicesManager;
  var SubnetsManager, VLANsManager, ConfigsManager, ManagerHelperService;
  let SearchService, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    DiscoveriesManager = $injector.get("DiscoveriesManager");
    DomainsManager = $injector.get("DomainsManager");
    MachinesManager = $injector.get("MachinesManager");
    DevicesManager = $injector.get("DevicesManager");
    SubnetsManager = $injector.get("SubnetsManager");
    VLANsManager = $injector.get("VLANsManager");
    ConfigsManager = $injector.get("ConfigsManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    SearchService = $injector.get("SearchService");
    RegionConnection = $injector.get("RegionConnection");

    // Mock buildSocket so an actual connection is not made.
    webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    spyOn(RegionConnection, "callMethod").and.returnValue($q.defer().promise);
  }));

  // Makes the DashboardController
  function makeController(loadManagerDefer) {
    var loadManagers = jest.spyOn(ManagerHelperService, "loadManagers");
    if (angular.isObject(loadManagerDefer)) {
      loadManagers.mockReturnValue(loadManagerDefer.promise);
    } else {
      loadManagers.mockReturnValue($q.defer().promise);
    }

    // Create the controller.
    var controller = $controller("DashboardController", {
      $scope: $scope,
      $rootScope: $rootScope,
      DiscoveriesManager: DiscoveriesManager,
      DomainsManager: DomainsManager,
      MachinesManager: MachinesManager,
      DevicesManager: DevicesManager,
      SubnetsManager: SubnetsManager,
      VLANsManager: VLANsManager,
      ConfigsManager: ConfigsManager,
      ManagerHelperService: ManagerHelperService
    });

    return controller;
  }

  it("sets title and page on $rootScope", function() {
    makeController();
    expect($rootScope.title).toBe("Dashboard");
    expect($rootScope.page).toBe("dashboard");
  });

  it("calls loadManagers with correct managers", function() {
    makeController();
    expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith($scope, [
      DiscoveriesManager,
      DomainsManager,
      MachinesManager,
      DevicesManager,
      SubnetsManager,
      VLANsManager,
      ConfigsManager
    ]);
  });

  it("sets initial $scope", function() {
    makeController();
    expect($scope.loaded).toBe(false);
    expect($scope.discoveredDevices).toBe(DiscoveriesManager.getItems());
    expect($scope.domains).toBe(DomainsManager.getItems());
    expect($scope.machines).toBe(MachinesManager.getItems());
    expect($scope.configManager).toBe(ConfigsManager);
    expect($scope.networkDiscovery).toBeNull();
    expect($scope.column).toBe("mac");
    expect($scope.selectedDevice).toBeNull();
    expect($scope.convertTo).toBeNull();
  });

  describe("proxyManager", function() {
    it("calls DevicesManager.createItem when device", function() {
      makeController();
      var sentinel = {};
      spyOn(DevicesManager, "createItem").and.returnValue(sentinel);
      $scope.convertTo = {
        type: "device"
      };
      var params = {};
      var observed = $scope.proxyManager.updateItem(params);
      expect(observed).toBe(sentinel);
      expect(DevicesManager.createItem).toHaveBeenCalledWith(params);
    });

    it("calls DevicesManager.createInterface when interface", function() {
      makeController();
      var sentinel = {};
      spyOn(DevicesManager, "createInterface").and.returnValue(sentinel);
      $scope.convertTo = {
        type: "interface"
      };
      var params = {};
      var observed = $scope.proxyManager.updateItem(params);
      expect(observed).toBe(sentinel);
      expect(DevicesManager.createInterface).toHaveBeenCalledWith(params);
    });
  });

  describe("getDiscoveryName", function() {
    it("returns discovery hostname", function() {
      makeController();
      var discovery = { hostname: "hostname" };
      expect($scope.getDiscoveryName(discovery)).toBe("hostname");
    });

    it("returns discovery mac_organization with device octets", function() {
      makeController();
      var discovery = {
        hostname: null,
        mac_organization: "mac-org",
        mac_address: "00:11:22:33:44:55"
      };
      var expected_name = "unknown";
      expect($scope.getDiscoveryName(discovery)).toBe(expected_name);
    });

    it("returns discovery with device mac", function() {
      makeController();
      var discovery = {
        hostname: null,
        mac_organization: null,
        mac_address: "00:11:22:33:44:55"
      };
      var expected_name = "unknown";
      expect($scope.getDiscoveryName(discovery)).toBe(expected_name);
    });
  });

  describe("getSubnetName", function() {
    it("calls SubnetsManager.getName with subnet", function() {
      makeController();
      var subnet = {
        id: makeInteger(0, 100)
      };
      var sentinel = {};
      SubnetsManager._items = [subnet];
      spyOn(SubnetsManager, "getName").and.returnValue(sentinel);
      expect($scope.getSubnetName(subnet.id)).toBe(sentinel);
      expect(SubnetsManager.getName).toHaveBeenCalledWith(subnet);
    });
  });

  describe("getVLANName", function() {
    it("calls VLANsManager.getName with vlan", function() {
      makeController();
      var vlan = {
        id: makeInteger(0, 100)
      };
      var sentinel = {};
      VLANsManager._items = [vlan];
      spyOn(VLANsManager, "getName").and.returnValue(sentinel);
      expect($scope.getVLANName(vlan.id)).toBe(sentinel);
      expect(VLANsManager.getName).toHaveBeenCalledWith(vlan);
    });
  });

  describe("toggleSelected", function() {
    it("clears selected if already selected", function() {
      makeController();
      var id = makeInteger(0, 100);
      $scope.selectedDevice = id;
      $scope.toggleSelected(id);
      expect($scope.selectedDevice).toBeNull();
    });

    it("sets selectedDevice and convertTo with static", function() {
      makeController();
      var id = makeInteger(0, 100);
      var defaultDomain = {
        id: 0
      };
      DomainsManager._items = [defaultDomain];
      var discovered = {
        first_seen: id,
        hostname: makeName("hostname"),
        subnet: makeInteger(0, 100)
      };
      DiscoveriesManager._items = [discovered];
      $scope.toggleSelected(id);
      expect($scope.selectedDevice).toBe(id);
      expect($scope.convertTo).toEqual({
        type: "device",
        hostname: $scope.getDiscoveryName(discovered),
        domain: defaultDomain,
        parent: null,
        ip_assignment: "dynamic",
        goTo: false,
        saved: false,
        deviceIPOptions: [
          ["static", "Static"],
          ["dynamic", "Dynamic"],
          ["external", "External"]
        ]
      });
    });
    it("sets handles fqdn correctly", function() {
      makeController();
      var id = makeInteger(0, 100);
      var defaultDomain = {
        id: 0
      };
      var domain = {
        id: 1,
        name: makeName("domain")
      };
      var hostname = makeName("hostname");
      DomainsManager._items = [defaultDomain, domain];
      var discovered = {
        first_seen: id,
        hostname: hostname + "." + domain.name,
        subnet: makeInteger(0, 100)
      };
      DiscoveriesManager._items = [discovered];
      $scope.toggleSelected(id);
      expect($scope.selectedDevice).toBe(id);
      // Just confirm the hostname and domain, the rest is checked in the
      // above test.
      expect($scope.convertTo.hostname).toBe(hostname);
      expect($scope.convertTo.domain).toBe(domain);
    });

    it("sets selectedDevice and convertTo without static", function() {
      makeController();
      var id = makeInteger(0, 100);
      var defaultDomain = {
        id: 0
      };
      DomainsManager._items = [defaultDomain];
      var discovered = {
        first_seen: id,
        hostname: makeName("hostname"),
        subnet: null
      };
      DiscoveriesManager._items = [discovered];
      $scope.toggleSelected(id);
      expect($scope.selectedDevice).toBe(id);
      expect($scope.convertTo).toEqual({
        type: "device",
        hostname: $scope.getDiscoveryName(discovered),
        domain: defaultDomain,
        parent: null,
        ip_assignment: "dynamic",
        goTo: false,
        saved: false,
        deviceIPOptions: [["dynamic", "Dynamic"], ["external", "External"]]
      });
    });
  });

  describe("sortTable", function() {
    it("sets predicate", function() {
      makeController();
      var predicate = makeName("predicate");
      $scope.sortTable(predicate);
      expect($scope.predicate).toBe(predicate);
    });

    it("reverses reverse", function() {
      makeController();
      $scope.reverse = true;
      $scope.sortTable(makeName("predicate"));
      expect($scope.reverse).toBe(false);
    });
  });

  describe("preProcess", function() {
    it("adjust device to include the needed fields", function() {
      makeController();
      var id = makeInteger(0, 100);
      var defaultDomain = {
        id: 0
      };
      DomainsManager._items = [defaultDomain];
      var discovered = {
        first_seen: id,
        hostname: makeName("hostname"),
        subnet: makeInteger(0, 100),
        mac_address: makeName("mac"),
        ip: makeName("ip")
      };
      DiscoveriesManager._items = [discovered];
      $scope.toggleSelected(id);
      var observed = $scope.preProcess($scope.convertTo);
      expect(observed).not.toBe($scope.convertTo);
      expect(observed).toEqual({
        type: "device",
        hostname: $scope.getDiscoveryName(discovered),
        domain: defaultDomain,
        parent: null,
        ip_assignment: "dynamic",
        goTo: false,
        saved: false,
        deviceIPOptions: [
          ["static", "Static"],
          ["dynamic", "Dynamic"],
          ["external", "External"]
        ],
        primary_mac: discovered.mac_address,
        extra_macs: [],
        interfaces: [
          {
            mac: discovered.mac_address,
            ip_assignment: "dynamic",
            ip_address: discovered.ip,
            subnet: discovered.subnet
          }
        ]
      });
    });

    it("adjust interface to include the needed fields", function() {
      makeController();
      var id = makeInteger(0, 100);
      var defaultDomain = {
        id: 0
      };
      DomainsManager._items = [defaultDomain];
      var discovered = {
        first_seen: id,
        hostname: makeName("hostname"),
        subnet: makeInteger(0, 100),
        mac_address: makeName("mac"),
        ip: makeName("ip")
      };
      DiscoveriesManager._items = [discovered];
      $scope.toggleSelected(id);
      $scope.convertTo.type = "interface";
      var observed = $scope.preProcess($scope.convertTo);
      expect(observed).not.toBe($scope.convertTo);
      expect(observed).toEqual({
        type: "interface",
        hostname: $scope.getDiscoveryName(discovered),
        domain: defaultDomain,
        parent: null,
        ip_assignment: "dynamic",
        goTo: false,
        saved: false,
        deviceIPOptions: [
          ["static", "Static"],
          ["dynamic", "Dynamic"],
          ["external", "External"]
        ],
        mac_address: discovered.mac_address,
        ip_address: discovered.ip,
        subnet: discovered.subnet
      });
    });
  });

  describe("afterSave", function() {
    it("removes item from DiscoveriesManager", function() {
      makeController();
      var id = makeInteger(0, 100);
      $scope.selectedDevice = id;
      $scope.convertTo = {
        goTo: false
      };
      spyOn(DiscoveriesManager, "_removeItem");
      var newObj = {
        hostname: makeName("hostname"),
        parent: makeName("parent")
      };
      $scope.afterSave(newObj);
      expect(DiscoveriesManager._removeItem).toHaveBeenCalledWith(id);
      expect($scope.convertTo.hostname).toBe(newObj.hostname);
      expect($scope.convertTo.parent).toBe(newObj.parent);
      expect($scope.convertTo.saved).toBe(true);
      expect($scope.selectedDevice).toBeNull();
    });

    it("doesn't call $location.path if not goTo", function() {
      makeController();
      var id = makeInteger(0, 100);
      $scope.selectedDevice = id;
      $scope.convertTo = {
        goTo: false
      };
      spyOn(DiscoveriesManager, "_removeItem");
      spyOn($location, "path");
      $scope.afterSave({
        hostname: makeName("hostname"),
        parent: makeName("parent")
      });
      expect($location.path).not.toHaveBeenCalled();
    });

    it("calls $location.path if goTo without parent", function() {
      makeController();
      var id = makeInteger(0, 100);
      $scope.selectedDevice = id;
      $scope.convertTo = {
        goTo: true
      };
      spyOn(DiscoveriesManager, "_removeItem");
      spyOn($location, "path");
      $scope.afterSave({
        hostname: makeName("hostname"),
        parent: null
      });
      expect($location.path).toHaveBeenCalledWith("/devices/");
    });

    it("calls $location.path if goTo with parent", function() {
      makeController();
      var id = makeInteger(0, 100);
      $scope.selectedDevice = id;
      $scope.convertTo = {
        goTo: true
      };
      spyOn(DiscoveriesManager, "_removeItem");
      spyOn($location, "path");
      var parent = makeName("parent");
      $scope.afterSave({
        hostname: makeName("hostname"),
        parent: parent
      });
      expect($location.path).toHaveBeenCalledWith("/device/" + parent);
    });
  });

  describe("removeDevice", function() {
    it("calls `removeDevice` in `DiscoveriesManager`", function() {
      makeController();
      var device = {
        ip: "127.0.0.1",
        mac_address: "00:25:96:FF:FE:12:34:56"
      };
      spyOn(DiscoveriesManager, "removeDevice");
      $scope.removeDevice(device);
      expect(DiscoveriesManager.removeDevice).toHaveBeenCalled();
      expect(DiscoveriesManager.removeDevice).toHaveBeenCalledWith(device);
    });
  });

  describe("removeAllDevices", function() {
    it("calls `removeDevices` in `DiscoveriesManager`", function() {
      makeController();
      var device = {
        ip: "127.0.0.1",
        mac_address: "00:25:96:FF:FE:12:34:56"
      };
      $scope.discoveredDevices.push(device);
      spyOn(DiscoveriesManager, "removeDevices").and.callFake(function() {
        var deferred = $q.defer();
        return deferred.promise;
      });
      $scope.removeAllDevices();
      expect(DiscoveriesManager.removeDevices).toHaveBeenCalled();
    });
  });

  describe("openClearDiscoveriesPanel", function() {
    it("sets `showClearDiscoveriesPanel` to `true`", function() {
      makeController();
      $scope.openClearDiscoveriesPanel();
      expect($scope.showClearDiscoveriesPanel).toBe(true);
    });
  });

  describe("closeClearDiscoveriesPanel", function() {
    it("sets `showClearDiscoveriesPanel` to `false`", function() {
      makeController();
      $scope.closeClearDiscoveriesPanel();
      expect($scope.showClearDiscoveriesPanel).toBe(false);
    });
  });

  describe("getCount", function() {
    it("gets count of specified objects", function() {
      makeController();
      var device = {
        ip: "127.0.0.1",
        mac_address: "00:25:96:FF:FE:12:34:56"
      };
      $scope.discoveredDevices.push(device);

      expect($scope.getCount("ip", "127.0.0.1")).toBe(1);
      expect($scope.getCount("ip", "213.0.0.1")).toBe(0);
    });
  });

  describe("dedupeMetadata", function() {
    it("dedupes metadata", function() {
      makeController();
      $scope.discoveredDevices = [
        {
          fabric_name: "fabric-0",
          vlan: 5001,
          rack: "bionic-maas",
          subnet: "172.16.1.0/24"
        },
        {
          fabric_name: "fabric-0",
          vlan: 5001,
          rack: "bionic-maas",
          subnet: "172.16.1.0/24"
        }
      ];

      expect($scope.dedupeMetadata("fabric_name")).toEqual([
        {
          fabric_name: "fabric-0",
          vlan: 5001,
          rack: "bionic-maas",
          subnet: "172.16.1.0/24"
        }
      ]);
    });
  });

  describe("toggleFilter", function() {
    it("calls SearchService.toggleFilter", function() {
      makeController();
      spyOn(SearchService, "toggleFilter").and.returnValue(
        SearchService.getEmptyFilter()
      );
      $scope.toggleFilter("hostname", "test");
      expect(SearchService.toggleFilter).toHaveBeenCalled();
    });

    it("sets $scope.filters", function() {
      makeController();
      var filters = { _: [], other: [] };
      spyOn(SearchService, "toggleFilter").and.returnValue(filters);
      $scope.toggleFilter("hostname", "test");
      expect($scope.filters).toBe(filters);
    });

    it("calls SearchService.filtersToString", function() {
      makeController();
      spyOn(SearchService, "filtersToString").and.returnValue("");
      $scope.toggleFilter("hostname", "test");
      expect(SearchService.filtersToString).toHaveBeenCalled();
    });

    it("sets $scope.search", function() {
      makeController();
      $scope.toggleFilter("hostname", "test");
      expect($scope.search).toBe("hostname:(=test)");
    });
  });

  describe("setMetadata", function() {
    it("sets metadata for fabrics, vlans, racks and subnets", function() {
      makeController();
      $scope.discoveredDevices = [
        {
          fabric_name: "fabric-01",
          vlan: 5001,
          observer_hostname: "happy-rack",
          subnet_cidr: "127.0.0.1/24"
        },
        {
          fabric_name: "fabric-02",
          vlan: 5002,
          observer_hostname: "happy-rack",
          subnet_cidr: "127.0.0.1/25"
        },
        {
          fabric_name: "fabric-03",
          vlan: 5002,
          observer_hostname: "happy-rack",
          subnet_cidr: "127.0.0.1/24"
        }
      ];

      $scope.setMetadata();

      expect($scope.metadata).toEqual({
        fabric: [
          { name: "fabric-01", count: 1 },
          { name: "fabric-02", count: 1 },
          { name: "fabric-03", count: 1 }
        ],
        vlan: [{ name: 5001, count: 1 }, { name: 5002, count: 2 }],
        rack: [{ name: "happy-rack", count: 3 }],
        subnet: [
          { name: "127.0.0.1/24", count: 2 },
          { name: "127.0.0.1/25", count: 1 }
        ]
      });
    });
  });

  describe("isFilterActive", function() {
    it("returns true when active", function() {
      makeController();
      $scope.toggleFilter("hostname", "test");
      expect($scope.isFilterActive("hostname", "test")).toBe(true);
    });

    it("returns false when inactive", function() {
      makeController();
      $scope.toggleFilter("hostname", "test2");
      expect($scope.isFilterActive("hostname", "test")).toBe(false);
    });
  });

  describe("updateFilters", function() {
    it("updates filters and sets searchValid to true", function() {
      makeController();
      $scope.search = "test hostname:name";
      $scope.updateFilters();
      expect($scope.filters).toEqual({
        _: ["test"],
        hostname: ["name"]
      });
      expect($scope.searchValid).toBe(true);
    });

    it("updates sets filters empty and sets searchValid to false", function() {
      makeController();
      $scope.search = "test hostname:(name";
      $scope.updateFilters();
      expect($scope.filters).toEqual(SearchService.getEmptyFilter());
      expect($scope.searchValid).toBe(false);
    });
  });
});
