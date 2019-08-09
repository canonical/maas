/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Details Controller
 */

export function filterSource() {
  return function(subnets, source) {
    var filtered = [];
    angular.forEach(subnets, function(subnet) {
      if (subnet.id !== source.id && subnet.version === source.version) {
        filtered.push(subnet);
      }
    });
    return filtered;
  };
}

/* @ngInject */
export function SubnetDetailsController(
  $scope,
  $rootScope,
  $routeParams,
  $location,
  ConfigsManager,
  SubnetsManager,
  SpacesManager,
  VLANsManager,
  UsersManager,
  FabricsManager,
  StaticRoutesManager,
  ManagerHelperService,
  ErrorService,
  ConverterService,
  DHCPSnippetsManager,
  GeneralManager
) {
  // Set title and page.
  $rootScope.title = "Loading...";

  // Note: this value must match the top-level tab, in order for
  // highlighting to occur properly.
  $rootScope.page = "networks";

  // Initial values.
  $scope.loaded = false;
  $scope.subnet = null;
  $scope.editSummary = false;
  $scope.active_discovery_data = null;
  $scope.active_discovery_interval = null;
  $scope.subnets = SubnetsManager.getItems();
  $scope.subnetManager = SubnetsManager;
  $scope.staticRoutes = StaticRoutesManager.getItems();
  $scope.staticRoutesManager = StaticRoutesManager;
  $scope.space = null;
  $scope.vlans = VLANsManager.getItems();
  $scope.fabrics = FabricsManager.getItems();
  $scope.actionError = null;
  $scope.actionOption = null;
  $scope.actionOptions = [];
  $scope.reverse = false;
  $scope.newStaticRoute = null;
  $scope.editStaticRoute = null;
  $scope.deleteStaticRoute = null;
  $scope.snippets = DHCPSnippetsManager.getItems();

  $scope.MAP_SUBNET_ACTION = {
    name: "map_subnet",
    title: "Map subnet"
  };
  $scope.DELETE_ACTION = {
    name: "delete",
    title: "Delete"
  };

  // Alloc type mapping.
  var ALLOC_TYPES = {
    0: "Automatic",
    1: "Static",
    4: "User reserved",
    5: "DHCP",
    6: "Observed"
  };

  // Node type mapping.
  var NODE_TYPES = {
    0: "Machine",
    1: "Device",
    2: "Rack controller",
    3: "Region controller",
    4: "Rack and region controller",
    5: "Chassis",
    6: "Storage"
  };

  // Updates the page title.
  function updateTitle() {
    const subnet = $scope.subnet;
    if (subnet && subnet.cidr) {
      $rootScope.title = subnet.cidr;
      if (subnet.name && subnet.cidr !== subnet.name) {
        $rootScope.title += " (" + subnet.name + ")";
      }
    }
  }

  // Update the IP version of the CIDR.
  function updateIPVersion() {
    var ip = $scope.subnet.cidr.split("/")[0];
    if (ip.indexOf(":") === -1) {
      $scope.ipVersion = 4;
    } else {
      $scope.ipVersion = 6;
    }
  }

  // Sort for IP address.
  $scope.ipSort = function(ipAddress) {
    if ($scope.ipVersion === 4) {
      return ConverterService.ipv4ToInteger(ipAddress.ip);
    } else {
      return ConverterService.ipv6Expand(ipAddress.ip);
    }
  };

  // Set default predicate to the ipSort function.
  $scope.predicate = $scope.ipSort;

  // Return the name of the allocation type.
  $scope.getAllocType = function(allocType) {
    var str = ALLOC_TYPES[allocType];
    if (angular.isString(str)) {
      return str;
    } else {
      return "Unknown";
    }
  };

  $scope.getSubnetCIDR = function(destId) {
    return SubnetsManager.getItemFromList(destId).cidr;
  };

  // Sort based on the name of the allocation type.
  $scope.allocTypeSort = function(ipAddress) {
    return $scope.getAllocType(ipAddress.alloc_type);
  };

  // Return the name of the node type for the given IP.
  $scope.getUsageForIP = function(ip) {
    if (angular.isObject(ip.node_summary)) {
      var isContainer = ip.node_summary.is_container;
      var nodeType = ip.node_summary.node_type;
      if (nodeType === 1 && isContainer === true) {
        return "Container";
      }
      var str = NODE_TYPES[nodeType];
      if (angular.isString(str)) {
        return str;
      } else {
        return "Unknown";
      }
    } else if (angular.isObject(ip.bmcs)) {
      return "BMC";
    } else if (angular.isObject(ip.dns_records)) {
      return "DNS";
    } else {
      return "Unknown";
    }
  };

  // Sort based on the node type string.
  $scope.nodeTypeSort = function(ipAddress) {
    return $scope.getUsageForIP(ipAddress);
  };

  // Sort based on the owner name.
  $scope.ownerSort = function(ipAddress) {
    var owner = ipAddress.user;
    if (angular.isString(owner) && owner.length > 0) {
      return owner;
    } else {
      return "MAAS";
    }
  };

  // Called to change the sort order of the IP table.
  $scope.sortIPTable = function(predicate) {
    $scope.predicate = predicate;
    $scope.reverse = !$scope.reverse;
  };

  // Return the name of the VLAN.
  $scope.getVLANName = function(vlan) {
    return VLANsManager.getName(vlan);
  };

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  $scope.actionRetry = function() {
    // When we clear actionError, the HTML will be re-rendered to
    // hide the error message (and the user will be taken back to
    // the previous action they were performing, since we reset
    // the actionOption in the error handler.
    $scope.actionError = null;
  };

  // Perform the action.
  $scope.actionGo = function() {
    if ($scope.actionOption.name === "map_subnet") {
      SubnetsManager.scanSubnet($scope.subnet).then(
        function(result) {
          if (result && result.scan_started_on.length === 0) {
            $scope.actionError = ManagerHelperService.parseValidationError(
              result.result
            );
          } else {
            $scope.actionOption = null;
            $scope.actionError = null;
          }
        },
        function(error) {
          $scope.actionError = ManagerHelperService.parseValidationError(error);
        }
      );
    } else if ($scope.actionOption.name === "delete") {
      SubnetsManager.deleteSubnet($scope.subnet).then(
        function(result) {
          $scope.actionOption = null;
          $scope.actionError = null;
          $location.path("/networks");
        },
        function(error) {
          $scope.actionError = ManagerHelperService.parseValidationError(error);
        }
      );
    }
  };

  // Called when a action is selected.
  $scope.actionChanged = function() {
    $scope.actionError = null;
  };

  // Called when the "Cancel" button is pressed.
  $scope.cancelAction = function() {
    $scope.actionOption = null;
    $scope.actionError = null;
  };

  // Called when the managers load to populate the actions the user
  // is allowed to perform.
  $scope.updateActions = function() {
    if (UsersManager.isSuperUser()) {
      $scope.actionOptions = [$scope.MAP_SUBNET_ACTION, $scope.DELETE_ACTION];
    } else {
      $scope.actionOptions = [];
    }
  };

  // Called when the "edit" button is cliked in the subnet summary
  $scope.enterEditSummary = function() {
    $scope.editSummary = true;
  };

  // Called when the "cancel" button is cliked in the subnet summary
  $scope.exitEditSummary = function() {
    $scope.editSummary = false;
  };

  // Called by maas-obj-form before it saves the subnet. The passed
  // subnet is the object right before its sent over the websocket.
  $scope.subnetPreSave = function(subnet, changedFields) {
    // Adjust the subnet object if the fabric changed.
    if (changedFields.indexOf("fabric") !== -1) {
      // Fabric changed, the websocket expects VLAN to be updated, so
      // we set the VLAN to the default VLAN for the new fabric.
      subnet.vlan = FabricsManager.getItemFromList(
        subnet.fabric
      ).default_vlan_id;
    }
    return subnet;
  };

  // Called to start adding a new static route.
  $scope.addStaticRoute = function() {
    $scope.editStaticRoute = null;
    $scope.deleteStaticRoute = null;
    $scope.newStaticRoute = {
      source: $scope.subnet.id,
      gateway_ip: "",
      destination: null,
      metric: 0
    };
  };

  // Cancel adding the new static route.
  $scope.cancelAddStaticRoute = function() {
    $scope.newStaticRoute = null;
  };

  // Return true if the static route is in edit mode.
  $scope.isStaticRouteInEditMode = function(route) {
    return $scope.editStaticRoute === route;
  };

  // Toggle edit mode for the static route.
  $scope.staticRouteToggleEditMode = function(route) {
    $scope.newStaticRoute = null;
    $scope.deleteStaticRoute = null;
    if ($scope.isStaticRouteInEditMode(route)) {
      $scope.editStaticRoute = null;
    } else {
      $scope.editStaticRoute = route;
    }
  };

  // Return true if the static route is in delete mode.
  $scope.isStaticRouteInDeleteMode = function(route) {
    return $scope.deleteStaticRoute === route;
  };

  // Enter delete mode for the static route.
  $scope.staticRouteEnterDeleteMode = function(route) {
    $scope.newStaticRoute = null;
    $scope.editStaticRoute = null;
    $scope.deleteStaticRoute = route;
  };

  // Exit delete mode for the statc route.
  $scope.staticRouteCancelDelete = function() {
    $scope.deleteStaticRoute = null;
  };

  // Perform the delete operation on the static route.
  $scope.staticRouteConfirmDelete = function() {
    StaticRoutesManager.deleteItem($scope.deleteStaticRoute).then(function() {
      $scope.deleteStaticRoute = null;
    });
  };

  $scope.getVLANOnSubnet = function(subnet, vlans) {
    if (!angular.isObject(subnet) && !angular.isArray(vlans)) {
      return;
    }

    return vlans.find(function(vlan) {
      return vlan.id === subnet.vlan;
    });
  };

  $scope.DHCPEnabled = function(subnet, vlans) {
    if (!angular.isObject(subnet) || !angular.isArray(vlans)) {
      return;
    }
    var vlanOnSubnet = $scope.getVLANOnSubnet(subnet, vlans);
    return vlanOnSubnet.dhcp_on;
  };

  $scope.hasIPAddresses = function(IPAddresses) {
    if (!angular.isArray(IPAddresses)) {
      return;
    }

    return IPAddresses.length ? true : false;
  };

  // Called when the subnet has been loaded.
  function subnetLoaded(subnet) {
    $scope.subnet = subnet;
    $scope.loaded = true;

    updateTitle();

    // Watch the vlan and fabric field so if its changed on the subnet
    // we make sure that the fabric is updated. It is possible that
    // fabric is removed from the subnet since it is injected from this
    // controller, so when it is removed we add it back.
    var updateFabric = function() {
      $scope.subnet.fabric = VLANsManager.getItemFromList(
        $scope.subnet.vlan
      ).fabric;
      $scope.subnet.fabric_name = FabricsManager.getItemFromList(
        subnet.fabric
      ).name;
    };
    var updateSpace = function() {
      $scope.space = SpacesManager.getItemFromList($scope.subnet.space);
    };
    var updateVlan = function() {
      var vlan = VLANsManager.getItemFromList($scope.subnet.vlan);
      $scope.subnet.vlan_name = VLANsManager.getName(vlan);
    };

    $scope.snippets.forEach(snippet => {
      let subnet = SubnetsManager.getItemFromList(snippet.subnet);

      if (subnet) {
        snippet.subnet_cidr = subnet.cidr;
      }
    });

    $scope.filteredSnippets = DHCPSnippetsManager.getFilteredSnippets(
      $scope.snippets,
      [$scope.subnet.cidr]
    );

    $scope.$watch("subnet.fabric", updateFabric);
    $scope.$watch("subnet.fabric_name", updateFabric);
    $scope.$watch("subnet.vlan", updateFabric);
    $scope.$watch("subnet.vlan_name", updateVlan);
    $scope.$watch("subnet.space", updateSpace);
    $scope.$watch("subnet.cidr", updateIPVersion);
  }

  // Load all the required managers.
  ManagerHelperService.loadManagers($scope, [
    ConfigsManager,
    SubnetsManager,
    SpacesManager,
    VLANsManager,
    UsersManager,
    FabricsManager,
    StaticRoutesManager,
    DHCPSnippetsManager
  ]).then(function() {
    $scope.updateActions();
    $scope.active_discovery_data = ConfigsManager.getItemFromList(
      "active_discovery_interval"
    );
    // Find active discovery interval
    angular.forEach($scope.active_discovery_data.choices, function(choice) {
      if (choice[0] === $scope.active_discovery_data.value) {
        $scope.active_discovery_interval = choice[1];
      }
    });

    // Possibly redirected from another controller that already had
    // this subnet set to active. Only call setActiveItem if not
    // already the activeItem.
    var activeSubnet = SubnetsManager.getActiveItem();
    var requestedSubnet = parseInt($routeParams.subnet_id, 10);
    if (isNaN(requestedSubnet)) {
      ErrorService.raiseError("Invalid subnet identifier.");
    } else if (
      angular.isObject(activeSubnet) &&
      activeSubnet.id === requestedSubnet
    ) {
      subnetLoaded(activeSubnet);
    } else {
      SubnetsManager.setActiveItem(requestedSubnet).then(
        function(subnet) {
          subnetLoaded(subnet);

          // Set flag for RSD navigation item.
          if (!$rootScope.showRSDLink) {
            GeneralManager.getNavigationOptions().then(
              res => ($rootScope.showRSDLink = res.rsd)
            );
          }
        },
        function(error) {
          ErrorService.raiseError(error);
        }
      );
    }
  });
}
