/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * IP Ranges directive.
 */

/* @ngInject */
function maasIpRanges(
  IPRangesManager,
  UsersManager,
  ManagerHelperService,
  ConverterService
) {
  return {
    restrict: "E",
    scope: {
      subnet: "=",
      vlan: "="
    },
    templateUrl: "static/partials/ipranges.html?v=" + MAAS_config.files_version,
    controller: IpRangesController
  };

  /* @ngInject */
  function IpRangesController($scope) {
    $scope.loading = true;
    $scope.ipranges = IPRangesManager.getItems();
    $scope.iprangeManager = IPRangesManager;
    $scope.newRange = null;
    $scope.editIPRange = null;
    $scope.deleteIPRange = null;
    $scope.MAAS_VERSION_NUMBER = IPRangesManager.formatMAASVersionNumber();

    $scope.RESERVE_RANGE = {
      name: "reserve_range",
      title: "Reserve range",
      selectedTitle: "Reserve range",
      objectName: "reserveRange"
    };

    $scope.RESERVE_DYNAMIC_RANGE = {
      name: "reserve_dynamic_range",
      title: "Reserve dynamic range",
      selectedTitle: "Reserve dynamic range",
      objectName: "reserveDynamicRange"
    };

    $scope.actionOptions = [$scope.RESERVE_RANGE, $scope.RESERVE_DYNAMIC_RANGE];

    $scope.actionChanged = function() {
      var actionOptionName = $scope.actionOption
        ? $scope.actionOption.name
        : null;

      if (actionOptionName === "reserve_range") {
        $scope.addRange("reserved");
      }

      if (actionOptionName === "reserve_dynamic_range") {
        $scope.addRange("dynamic");
      }
    };

    // Return true if the authenticated user is super user.
    $scope.isSuperUser = function() {
      return UsersManager.isSuperUser();
    };

    // Called to start adding a new IP range.
    $scope.addRange = function(type) {
      $scope.newRange = {
        type: type,
        start_ip: "",
        end_ip: "",
        comment: ""
      };
      if (angular.isObject($scope.subnet)) {
        $scope.newRange.subnet = $scope.subnet.id;
      }
      if (angular.isObject($scope.vlan)) {
        $scope.newRange.vlan = $scope.vlan.id;
      }
      if (type === "dynamic") {
        $scope.newRange.comment = "Dynamic";
      }
    };

    // Cancel adding the new IP range.
    $scope.cancelAddRange = function() {
      $scope.newRange = null;
      $scope.actionOption = null;
    };

    // Return true if the IP range can be modified by the
    // authenticated user.
    $scope.ipRangeCanBeModified = function(range) {
      if ($scope.isSuperUser()) {
        return true;
      } else {
        // Can only modify reserved and same user.
        return (
          range.type === "reserved" &&
          range.user === UsersManager.getAuthUser().id
        );
      }
    };

    // Return true if the IP range is in edit mode.
    $scope.isIPRangeInEditMode = function(range) {
      return $scope.editIPRange === range;
    };

    // Toggle edit mode for the IP range.
    $scope.ipRangeToggleEditMode = function(range) {
      $scope.deleteIPRange = null;
      if ($scope.isIPRangeInEditMode(range)) {
        $scope.editIPRange = null;
      } else {
        $scope.editIPRange = range;
      }
    };

    // Clear edit mode for the IP range.
    $scope.ipRangeClearEditMode = function() {
      $scope.editIPRange = null;
    };

    // Return true if the IP range is in delete mode.
    $scope.isIPRangeInDeleteMode = function(range) {
      return $scope.deleteIPRange === range;
    };

    // Enter delete mode for the IP range.
    $scope.ipRangeEnterDeleteMode = function(range) {
      $scope.editIPRange = null;
      $scope.deleteIPRange = range;
    };

    // Exit delete mode for the IP range.
    $scope.ipRangeCancelDelete = function() {
      $scope.deleteIPRange = null;
    };

    // Perform the delete operation on the IP range.
    $scope.ipRangeConfirmDelete = function() {
      IPRangesManager.deleteItem($scope.deleteIPRange).then(function() {
        $scope.deleteIPRange = null;
      });
    };

    // Sort ranges by starting IP address.
    $scope.ipRangeSort = function(range) {
      if (range.start_ip.indexOf(":") !== -1) {
        return ConverterService.ipv6Expand(range.start_ip);
      } else {
        return ConverterService.ipv4ToInteger(range.start_ip);
      }
    };

    // Load the required managers.
    ManagerHelperService.loadManagers($scope, [
      IPRangesManager,
      UsersManager
    ]).then(function() {
      $scope.loading = false;
    });
  }
}

export default maasIpRanges;
