/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Networks List Controller
 */

/* @ngInject */
function NetworksListController(
  $scope,
  $rootScope,
  $filter,
  $location,
  SubnetsManager,
  FabricsManager,
  SpacesManager,
  VLANsManager,
  UsersManager,
  ManagerHelperService,
  GeneralManager
) {
  // Load the filters that are used inside the controller.
  var filterByVLAN = $filter("filterByVLAN");
  var filterByFabric = $filter("filterByFabric");
  var filterBySpace = $filter("filterBySpace");
  var filterByNullSpace = $filter("filterByNullSpace");

  // Set title and page.
  $rootScope.title = "Subnets";
  $rootScope.page = "networks";

  // Set the initial value of $scope.groupBy based on the URL
  // parameters, but default to the 'fabric' groupBy if it's not found.
  $scope.getURLParameters = function() {
    if (angular.isString($location.search().by)) {
      $scope.groupBy = $location.search().by;
    } else {
      $scope.groupBy = "fabric";
    }
  };

  $scope.ADD_FABRIC_ACTION = {
    name: "add_fabric",
    title: "Fabric",
    selectedTitle: "Add fabric",
    objectName: "fabric"
  };
  $scope.ADD_VLAN_ACTION = {
    name: "add_vlan",
    title: "VLAN",
    selectedTitle: "Add VLAN",
    objectName: "vlan"
  };
  $scope.ADD_SPACE_ACTION = {
    name: "add_space",
    title: "Space",
    selectedTitle: "Add space",
    objectName: "space"
  };
  $scope.ADD_SUBNET_ACTION = {
    name: "add_subnet",
    title: "Subnet",
    selectedTitle: "Add subnet",
    objectName: "subnet"
  };

  $scope.getURLParameters();

  // Set initial values.
  $scope.subnetManager = SubnetsManager;
  $scope.subnets = SubnetsManager.getItems();
  $scope.fabricManager = FabricsManager;
  $scope.fabrics = FabricsManager.getItems();
  $scope.spaceManager = SpacesManager;
  $scope.spaces = SpacesManager.getItems();
  $scope.vlanManager = VLANsManager;
  $scope.vlans = VLANsManager.getItems();
  $scope.loading = true;

  $scope.group = {};
  // Used when grouping by fabrics.
  $scope.group.fabrics = {};
  // User when grouping by spaces.
  $scope.group.spaces = {};
  $scope.group.spaces.orphanVLANs = [];

  // Initializers for action objects.
  var actionObjectInitializers = {
    fabric: function() {
      return {};
    },
    vlan: function() {
      // Set initial fabric.
      return {
        fabric: $scope.fabrics[0].id
      };
    },
    space: function() {
      return {};
    },
    subnet: function() {
      // Set initial VLAN and space.
      return {
        vlan: $scope.fabrics[0].vlan_ids[0]
      };
    }
  };

  // Return the name of the subnet.
  function getSubnetName(subnet) {
    return SubnetsManager.getName(subnet);
  }

  // Generate a table that can be easily rendered in the view.
  // Traverses the fabrics and VLANs in-order so that if previous
  // fabrics and VLANs' names are identical, they can be hidden from
  // the table cell.
  function updateFabricsGroupBy() {
    const rows = [];
    const previous_fabric = { id: -1 };
    const previous_vlan = { id: -1 };
    const fabrics = $filter("orderBy")($scope.fabrics, ["name"]);

    fabrics.forEach(fabric => {
      const vlans = $filter("orderBy")(filterByFabric($scope.vlans, fabric), [
        "vid"
      ]);

      vlans.forEach(vlan => {
        const subnets = filterByVLAN($scope.subnets, vlan);

        if (subnets.length) {
          subnets.forEach(subnet => {
            const space = SpacesManager.getItemFromList(subnet.space);
            const row = {
              dhcp: $scope.getDHCPStatus(vlan),
              fabric,
              fabric_name: "",
              space,
              subnet,
              subnet_name: getSubnetName(subnet),
              vlan,
              vlan_name: ""
            };
            if (fabric.id !== previous_fabric.id) {
              previous_fabric.id = fabric.id;
              row.fabric_name = fabric.name;
            }
            if (vlan.id !== previous_vlan.id) {
              previous_vlan.id = vlan.id;
              row.vlan_name = $scope.getVLANName(vlan);
            }
            rows.push(row);
          });
        } else {
          const space = SpacesManager.getItemFromList(vlan.space);
          const row = {
            dhcp: $scope.getDHCPStatus(vlan),
            fabric,
            fabric_name: "",
            space,
            vlan,
            vlan_name: $scope.getVLANName(vlan)
          };
          if (fabric.id !== previous_fabric.id) {
            previous_fabric.id = fabric.id;
            row.fabric_name = fabric.name;
          }
          rows.push(row);
        }
      });
    });
    $scope.group.fabrics.rows = rows;
  }

  // Generate a table that can be easily rendered in the view.
  // Traverses the spaces in-order so that if the previous space's name
  // is identical, it can be hidden from the table cell.
  // Note that this view only shows items that can be related to a space.
  // That is, VLANs and fabrics with no corresponding subnets (and
  // therefore spaces) cannot be shown in this table.
  function updateSpacesGroupBy() {
    var rows = [];
    var spaces = $filter("orderBy")($scope.spaces, ["name"]);
    var previous_space = { id: -1 };
    angular.forEach(spaces, function(space) {
      var subnets = filterBySpace($scope.subnets, space);
      subnets = $filter("orderBy")(subnets, ["cidr"]);
      var index = 0;
      angular.forEach(subnets, function(subnet) {
        index++;
        var vlan = VLANsManager.getItemFromList(subnet.vlan);
        var fabric = FabricsManager.getItemFromList(vlan.fabric);
        var row = {
          dhcp: $scope.getDHCPStatus(vlan),
          fabric: fabric,
          vlan: vlan,
          vlan_name: $scope.getVLANName(vlan),
          subnet: subnet,
          subnet_name: getSubnetName(subnet),
          space: space,
          space_name: ""
        };
        if (space.id !== previous_space.id) {
          previous_space.id = space.id;
          row.space_name = space.name;
        }
        rows.push(row);
      });
      if (index === 0) {
        rows.push({
          space: space,
          space_name: space.name
        });
      }
    });
    $scope.group.spaces.rows = rows;
  }

  function updateOrphanVLANs() {
    var rows = [];
    var subnets = filterByNullSpace($scope.subnets);
    subnets = $filter("orderBy")(subnets, ["cidr"]);
    angular.forEach(subnets, function(subnet) {
      var vlan = VLANsManager.getItemFromList(subnet.vlan);
      var fabric = FabricsManager.getItemFromList(vlan.fabric);
      var row = {
        dhcp: $scope.getDHCPStatus(vlan),
        fabric: fabric,
        vlan: vlan,
        vlan_name: $scope.getVLANName(vlan),
        subnet: subnet,
        subnet_name: getSubnetName(subnet),
        space: null
      };
      rows.push(row);
    });
    $scope.group.spaces.orphanVLANs = rows;
  }

  // Update the "Group by" selection. This is called from a few places:
  // * When the $watch notices data has changed
  // * When the URL bar is updated, after the URL is parsed and
  //   $scope.groupBy is updated
  // * When the drop-down "Group by" selection box changes
  $scope.updateGroupBy = function() {
    var groupBy = $scope.groupBy;
    if (groupBy === "space") {
      $location.search("by", "space");
      updateSpacesGroupBy();
      updateOrphanVLANs();
    } else {
      // The only other option is 'fabric', but in case the user
      // made a typo on the URL bar we just assume it was 'fabric'
      // as a fallback.
      $location.search("by", "fabric");
      updateFabricsGroupBy();
    }
  };

  // Called when the managers load to populate the actions the user
  // is allowed to perform.
  $scope.updateActions = function() {
    if (UsersManager.isSuperUser()) {
      $scope.actionOptions = [
        $scope.ADD_FABRIC_ACTION,
        $scope.ADD_VLAN_ACTION,
        $scope.ADD_SPACE_ACTION,
        $scope.ADD_SUBNET_ACTION
      ];
    } else {
      $scope.actionOptions = [];
    }
  };

  // Called when a action is selected.
  $scope.actionChanged = function() {
    $scope.newObject = actionObjectInitializers[
      $scope.actionOption.objectName
    ]();
  };

  // Called when the "Cancel" button is pressed.
  $scope.cancelAction = function() {
    $scope.actionOption = null;
    $scope.newObject = null;
  };

  // Return the name name for the VLAN.
  $scope.getVLANName = function(vlan) {
    return VLANsManager.getName(vlan);
  };

  // Return the name of the fabric from its given ID.
  $scope.getFabricNameById = function(fabricId) {
    return FabricsManager.getName(FabricsManager.getItemFromList(fabricId));
  };

  // Called before the subnet object is saved. Sets the fabric
  // field to be the fabric for the selected VLAN.
  $scope.actionSubnetPreSave = function(obj) {
    obj.fabric = VLANsManager.getItemFromList(obj.vlan).fabric;
    return obj;
  };

  $scope.getDHCPStatus = vlan => {
    if (vlan.external_dhcp) {
      return `External (${vlan.external_dhcp})`;
    }

    if (vlan.dhcp_on) {
      return "MAAS-provided";
    }

    return "No DHCP";
  };

  ManagerHelperService.loadManagers($scope, [
    SubnetsManager,
    FabricsManager,
    SpacesManager,
    VLANsManager,
    UsersManager
  ]).then(function() {
    $scope.loading = false;

    // Set flag for RSD navigation item.
    if (!$rootScope.showRSDLink) {
      GeneralManager.getNavigationOptions().then(
        res => ($rootScope.showRSDLink = res.rsd)
      );
    }

    $scope.updateActions();

    $scope.$watch(
      "[subnets, fabrics, spaces, vlans]",
      $scope.updateGroupBy,
      true
    );

    // If the route has been updated, a new search string must
    // potentially be rendered.
    $scope.$on("$routeUpdate", function() {
      $scope.getURLParameters();
      $scope.updateGroupBy();
    });
    $scope.updateGroupBy();
  });
}

export default NetworksListController;
