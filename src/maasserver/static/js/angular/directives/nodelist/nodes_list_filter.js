/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Directive for nodes list filter dropdown.
 *
 */

// Map of names displayed in the UI for each metadata option
const displayNames = new Map([
  ["architecture", "Architecture"],
  ["fabric", "Fabric"],
  ["fabrics", "Fabric"],
  ["owner", "Owner"],
  ["pod", "KVM"],
  ["pool", "Resource pool"],
  ["rack", "Rack"],
  ["release", "OS/Release"],
  ["spaces", "Space"],
  ["status", "Status"],
  ["storage_tags", "Storage tags"],
  ["subnet", "Subnet"],
  ["subnets", "Subnet"],
  ["tags", "Tags"],
  ["vlan", "VLAN"],
  ["zone", "Zone"]
]);

// Map of metadata names that use a different name for filtering
const metadataNames = new Map([
  ["fabric", "fabric_name"],
  ["rack", "observer_hostname"],
  ["subnet", "subnet_cidr"]
]);

/* @ngInject */
function nodesListFilter($document) {
  return {
    restrict: "E",
    scope: {
      currentPage: "<",
      isDisabled: "<",
      isFilterActive: "<",
      options: "<",
      order: "<",
      toggleFilter: "<"
    },
    templateUrl: "static/partials/nodelist/nodes-list-filter.html",
    link: function(scope, element) {
      scope.clickHandler = event => {
        const clickedInsideElement = element.find(event.target).length > 0;

        if (clickedInsideElement) {
          return;
        }
        scope.$apply(() => (scope.openFilter = false));
      };

      $document.on("click", scope.clickHandler);
      scope.$on("$destroy", () => $document.off("click", scope.clickHandler));
    },
    controller: NodesListFilterController
  };
}

/* @ngInject */
function NodesListFilterController($scope) {
  $scope.openFilter = false;
  $scope.openOption = "";
  $scope.orderedOptions = [];

  $scope.toggleOpenFilter = () => {
    $scope.openFilter = !$scope.openFilter;
  };

  $scope.toggleOpenOption = option => {
    $scope.openOption = $scope.openOption === option ? "" : option;
  };

  $scope.orderOptions = () => {
    const { options, order } = $scope;
    // Convert metadata object into array and order
    return order.map(key => ({
      name: metadataNames.get(key) || key,
      displayName: displayNames.get(key) || key,
      entries: options[key] || []
    }));
  };

  $scope.$watch(
    "options",
    () => {
      $scope.orderedOptions = $scope.orderOptions();
    },
    true
  );
}

export default nodesListFilter;
