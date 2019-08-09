/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Fabric Details Controller
 */

/* @ngInject */
function FabricDetailsController(
  $scope,
  $rootScope,
  $routeParams,
  $filter,
  $location,
  FabricsManager,
  VLANsManager,
  SubnetsManager,
  SpacesManager,
  ControllersManager,
  UsersManager,
  ManagerHelperService,
  ErrorService,
  GeneralManager
) {
  // Set title and page.
  $rootScope.title = "Loading...";

  // Note: this value must match the top-level tab, in order for
  // highlighting to occur properly.
  $rootScope.page = "networks";

  // Initial values.
  $scope.fabric = null;
  $scope.fabricManager = FabricsManager;
  $scope.editSummary = false;
  $scope.vlans = VLANsManager.getItems();
  $scope.subnets = SubnetsManager.getItems();
  $scope.controllers = ControllersManager.getItems();
  $scope.loaded = false;

  // Updates the page title.
  function updateTitle() {
    $rootScope.title = $scope.fabric.name;
  }

  // Called when the "edit" button is cliked in the fabric summary
  $scope.enterEditSummary = function() {
    $scope.editSummary = true;
  };

  // Called when the "cancel" button is cliked in the fabric summary
  $scope.exitEditSummary = function() {
    $scope.editSummary = false;
  };

  // Called when the fabric has been loaded.
  function fabricLoaded(fabric) {
    if (angular.isObject(fabric)) {
      $scope.fabric = fabric;
      updateTitle();
      $scope.$watch("vlans", updateVLANs, true);
      $scope.$watch("subnets", updateVLANs, true);
      $scope.$watch("controllers", updateVLANs, true);
      $scope.loaded = true;
      // Initial table sort order.
      $scope.predicate = "['vlan_name', 'vlan.id', 'subnet_name']";
    }
  }

  // Generate a table that can easily be rendered in the view.
  function updateVLANs() {
    var rows = [];
    var racks = {};
    angular.forEach(
      $filter("filter")($scope.vlans, { fabric: $scope.fabric.id }, true),
      function(vlan) {
        var subnets = $filter("filter")(
          $scope.subnets,
          { vlan: vlan.id },
          true
        );
        if (subnets.length > 0) {
          angular.forEach(subnets, function(subnet) {
            var space = SpacesManager.getItemFromList(subnet.space);
            var space_name = space === null ? "(undefined)" : space.name;
            var row = {
              vlan: vlan,
              vlan_name: VLANsManager.getName(vlan),
              subnet: subnet,
              subnet_name: SubnetsManager.getName(subnet),
              space: space,
              space_name: space_name
            };
            rows.push(row);
          });
        } else {
          // If there are no subnets, populate a row based on the
          // information we have (just the VLAN).
          var row = {
            vlan: vlan,
            vlan_name: VLANsManager.getName(vlan),
            subnet: null,
            subnet_name: null,
            space: null,
            space_name: null
          };
          rows.push(row);
        }
        // Enumerate racks for vlan.
        angular.forEach(vlan.rack_sids, function(rack_sid) {
          var rack = ControllersManager.getItemFromList(rack_sid);
          if (angular.isObject(rack)) {
            racks[rack.system_id] = rack;
          }
        });
      }
    );
    $scope.rows = rows;
    $scope.racks = Object.keys(racks).map(function(key) {
      return racks[key];
    });
  }

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Return true if this is the default Fabric
  $scope.isDefaultFabric = function() {
    if (!angular.isObject($scope.fabric)) {
      return false;
    }
    return $scope.fabric.id === 0;
  };

  // Called to check if the space can be deleted.
  $scope.canBeDeleted = function() {
    if (angular.isObject($scope.fabric)) {
      return $scope.fabric.id !== 0;
    }
    return false;
  };

  // Called when the delete fabric button is pressed.
  $scope.deleteButton = function() {
    $scope.error = null;
    $scope.confirmingDelete = true;
  };

  // Called when the cancel delete fabric button is pressed.
  $scope.cancelDeleteButton = function() {
    $scope.confirmingDelete = false;
  };

  // Called when the confirm delete fabric button is pressed.
  $scope.deleteConfirmButton = function() {
    FabricsManager.deleteFabric($scope.fabric).then(
      function() {
        $scope.confirmingDelete = false;
        $location.path("/networks");
        $location.search("by", "fabric");
      },
      function(reply) {
        $scope.error = ManagerHelperService.parseValidationError(reply.error);
      }
    );
  };

  // Load all the required managers.
  ManagerHelperService.loadManagers($scope, [
    FabricsManager,
    VLANsManager,
    SubnetsManager,
    SpacesManager,
    ControllersManager,
    UsersManager
  ]).then(function() {
    // Possibly redirected from another controller that already had
    // this fabric set to active. Only call setActiveItem if not
    // already the activeItem.
    var activeFabric = FabricsManager.getActiveItem();
    var requestedFabric = parseInt($routeParams.fabric_id, 10);

    if (isNaN(requestedFabric)) {
      ErrorService.raiseError("Invalid fabric identifier.");
    } else if (
      angular.isObject(activeFabric) &&
      activeFabric.id === requestedFabric
    ) {
      fabricLoaded(activeFabric);

      // Set flag for RSD navigation item.
      if (!$rootScope.showRSDLink) {
        GeneralManager.getNavigationOptions().then(
          res => ($rootScope.showRSDLink = res.rsd)
        );
      }
    } else {
      FabricsManager.setActiveItem(requestedFabric).then(
        function(fabric) {
          fabricLoaded(fabric);
        },
        function(error) {
          ErrorService.raiseError(error);
        }
      );
    }
  });
}

export default FabricDetailsController;
