/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Dashboard Controller
 */

/* @ngInject */
function DashboardController(
  $scope,
  $rootScope,
  $location,
  DiscoveriesManager,
  DomainsManager,
  MachinesManager,
  DevicesManager,
  SubnetsManager,
  VLANsManager,
  ConfigsManager,
  ManagerHelperService,
  SearchService,
  GeneralManager
) {
  // Default device IP options.
  var deviceIPOptions = [
    ["static", "Static"],
    ["dynamic", "Dynamic"],
    ["external", "External"]
  ];

  // Set title and page.
  $rootScope.title = "Dashboard";
  $rootScope.page = "dashboard";

  // Set initial values.
  $scope.loaded = false;
  $scope.discoveredDevices = DiscoveriesManager.getItems();
  $scope.domains = DomainsManager.getItems();
  $scope.machines = MachinesManager.getItems();
  $scope.devices = DevicesManager.getItems();
  $scope.configManager = ConfigsManager;
  $scope.networkDiscovery = null;
  $scope.column = "mac";
  $scope.selectedDevice = null;
  $scope.convertTo = null;
  $scope.showClearDiscoveriesPanel = false;
  $scope.removingDevices = false;
  $scope.MAAS_VERSION_NUMBER = DiscoveriesManager.formatMAASVersionNumber();
  $scope.search = "";
  $scope.searchValid = true;
  $scope.actionOption = null;
  $scope.filters = SearchService.getEmptyFilter();
  $scope.metadata = {};
  $scope.filteredDevices = [];

  $scope.clearSearch = function() {
    $scope.search = "";
    $scope.updateFilters();
  };

  $scope.filteredDevices = [];

  $scope.updateFilters = function() {
    var searchQuery = $scope.search;
    var filters = SearchService.getCurrentFilters(searchQuery);
    if (filters === null) {
      $scope.filters = SearchService.getEmptyFilter();
      $scope.searchValid = false;
    } else {
      $scope.filters = filters;
      $scope.searchValid = true;
    }
  };

  $scope.dedupeMetadata = function(prop) {
    return $scope.discoveredDevices.filter(function(item, pos, arr) {
      return (
        arr
          .map(function(obj) {
            return obj[prop];
          })
          .indexOf(item[prop]) === pos
      );
    });
  };

  $scope.getCount = function(prop, value) {
    return $scope.discoveredDevices.filter(function(item) {
      return item[prop] === value;
    }).length;
  };

  $scope.setMetadata = function() {
    var fabrics = $scope.dedupeMetadata("fabric_name").map(function(item) {
      return {
        name: item.fabric_name,
        count: $scope.getCount("fabric_name", item.fabric_name)
      };
    });

    var vlans = $scope.dedupeMetadata("vlan").map(function(item) {
      return {
        name: item.vlan,
        count: $scope.getCount("vlan", item.vlan)
      };
    });

    var racks = $scope.dedupeMetadata("observer_hostname").map(function(item) {
      return {
        name: item.observer_hostname,
        count: $scope.getCount("observer_hostname", item.observer_hostname)
      };
    });

    var subnets = $scope.dedupeMetadata("subnet_cidr").map(function(item) {
      return {
        name: item.subnet_cidr,
        count: $scope.getCount("subnet_cidr", item.subnet_cidr)
      };
    });

    $scope.metadata = {
      fabric: fabrics,
      vlan: vlans,
      rack: racks,
      subnet: subnets
    };
  };

  // Adds or removes a filter to the search.
  $scope.toggleFilter = function(type, value) {
    $scope.filters = SearchService.toggleFilter(
      $scope.filters,
      type,
      value,
      true
    );
    $scope.search = SearchService.filtersToString($scope.filters);
  };

  // Return True if the filter is active.
  $scope.isFilterActive = function(type, value) {
    return SearchService.isFilterActive($scope.filters, type, value, true);
  };

  $scope.formatMAASVersionNumber = function() {
    if (MAAS_config.version) {
      var versionWithPoint = MAAS_config.version.split(" ")[0];

      if (versionWithPoint) {
        if (versionWithPoint.split(".")[2] === "0") {
          return (
            versionWithPoint.split(".")[0] +
            "." +
            versionWithPoint.split(".")[1]
          );
        } else {
          return versionWithPoint;
        }
      }
    }
  };

  $scope.MAAS_VERSION_NUMBER = $scope.formatMAASVersionNumber();

  // Set default predicate to last_seen.
  $scope.predicate = $scope.last_seen;

  // Open clear devices panel
  $scope.openClearDiscoveriesPanel = function() {
    $scope.showClearDiscoveriesPanel = true;
  };

  // Close clear devices panel
  $scope.closeClearDiscoveriesPanel = function() {
    $scope.showClearDiscoveriesPanel = false;
  };

  // Sorts the table by predicate.
  $scope.sortTable = function(predicate) {
    $scope.predicate = predicate;
    $scope.reverse = !$scope.reverse;
  };

  // Proxy manager that the maas-obj-form directive uses to call the
  // correct method based on current type.
  $scope.proxyManager = {
    updateItem: function(params) {
      if ($scope.convertTo.type === "device") {
        return DevicesManager.createItem(params);
      } else if ($scope.convertTo.type === "interface") {
        return DevicesManager.createInterface(params);
      } else {
        throw new Error("Unknown type: " + $scope.convertTo.type);
      }
    }
  };

  // Return the name name for the Discovery.
  $scope.getDiscoveryName = function(discovery) {
    if (discovery.hostname === null) {
      return "unknown";
    } else {
      return discovery.hostname;
    }
  };

  // Get the name of the subnet from its ID.
  $scope.getSubnetName = function(subnetId) {
    var subnet = SubnetsManager.getItemFromList(subnetId);
    return SubnetsManager.getName(subnet);
  };

  // Get the name of the VLAN from its ID.
  $scope.getVLANName = function(vlanId) {
    var vlan = VLANsManager.getItemFromList(vlanId);
    return VLANsManager.getName(vlan);
  };

  // Remove device
  $scope.removeDevice = function(device) {
    device.isBeingRemoved = true;
    DiscoveriesManager.removeDevice(device);
  };

  // Remove all devices
  $scope.removeAllDevices = function() {
    $scope.removingDevices = true;
    DiscoveriesManager.removeDevices($scope.discoveredDevices).then(function() {
      $scope.discoveredDevices = DiscoveriesManager.getItems();
    });
  };

  // Sets selected device
  $scope.toggleSelected = function(deviceId) {
    if ($scope.selectedDevice === deviceId) {
      $scope.selectedDevice = null;
    } else {
      var discovered = DiscoveriesManager.getItemFromList(deviceId);
      var hostname = $scope.getDiscoveryName(discovered);
      var domain;
      if (hostname === "unknown") {
        hostname = "";
      }
      if (hostname.indexOf(".") > 0) {
        domain = DomainsManager.getDomainByName(
          hostname.slice(hostname.indexOf(".") + 1)
        );
        hostname = hostname.split(".", 1)[0];
        if (domain === null) {
          domain = DomainsManager.getDefaultDomain();
        }
      } else {
        domain = DomainsManager.getDefaultDomain();
      }
      $scope.convertTo = {
        type: "device",
        hostname: hostname,
        domain: domain,
        parent: null,
        ip_assignment: "dynamic",
        goTo: false,
        saved: false,
        deviceIPOptions: deviceIPOptions.filter(function(option) {
          // Filter the options to not include static if
          // a subnet is not defined for this discovered
          // item.
          if (option[0] === "static" && !angular.isNumber(discovered.subnet)) {
            return false;
          } else {
            return true;
          }
        })
      };
      $scope.selectedDevice = deviceId;
    }
  };

  // Called before the createItem is called to adjust the values
  // passed over the call.
  $scope.preProcess = function(item) {
    var discovered = DiscoveriesManager.getItemFromList($scope.selectedDevice);
    item = angular.copy(item);
    if ($scope.convertTo.type === "device") {
      item.primary_mac = discovered.mac_address;
      item.extra_macs = [];
      item.interfaces = [
        {
          mac: discovered.mac_address,
          ip_assignment: item.ip_assignment,
          ip_address: discovered.ip,
          subnet: discovered.subnet
        }
      ];
    } else if ($scope.convertTo.type === "interface") {
      item.mac_address = discovered.mac_address;
      item.ip_address = discovered.ip;
      item.subnet = discovered.subnet;
    }
    return item;
  };

  // Called after the createItem has been successful.
  $scope.afterSave = function(obj) {
    DiscoveriesManager._removeItem($scope.selectedDevice);
    $scope.selectedDevice = null;
    $scope.convertTo.hostname = obj.hostname;
    $scope.convertTo.parent = obj.parent;
    $scope.convertTo.saved = true;
    if ($scope.convertTo.goTo) {
      if (angular.isString(obj.parent)) {
        $location.path("/device/" + obj.parent);
      } else {
        $location.path("/devices/");
      }
    }
  };

  // Load all the managers and get the network discovery config item.
  ManagerHelperService.loadManagers($scope, [
    DiscoveriesManager,
    DomainsManager,
    MachinesManager,
    DevicesManager,
    SubnetsManager,
    VLANsManager,
    ConfigsManager
  ]).then(function() {
    $scope.loaded = true;

    // Set flag for RSD navigation item.
    if (!$rootScope.showRSDLink) {
      GeneralManager.getNavigationOptions().then(
        res => ($rootScope.showRSDLink = res.rsd)
      );
    }

    $scope.networkDiscovery = ConfigsManager.getItemFromList(
      "network_discovery"
    );

    $scope.setMetadata();

    $scope.discoveredDevices.forEach(function(device) {
      var date = new Date(device.last_seen);
      device.last_seen_timestamp = date.getTime();
    });

    $scope.$watchCollection("discoveredDevices", function() {
      $scope.removingDevices = false;
      $scope.closeClearDiscoveriesPanel();
    });
  });
}

export default DashboardController;
