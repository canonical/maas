/* Copyright 2019 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * DHCP snippets table directive.
 */

/* @ngInject */
function maasDhcpSnippetsTable($window) {
  return {
    restrict: "E",
    scope: {
      snippets: "=",
      allowAddNew: "=",
      allowDelete: "=",
      hideAllSnippetsLink: "="
    },
    templateUrl:
      "static/partials/dhcp-snippets-table.html?v=" +
      $window.MAAS_config.files_version,
    controller: DHCPSnippetsTableController
  };
}

/* @ngInject */
function DHCPSnippetsTableController(
  $scope,
  $log,
  SubnetsManager,
  MachinesManager,
  DevicesManager,
  ControllersManager,
  DHCPSnippetsManager
) {
  // Initial values.
  $scope.snippetsManager = DHCPSnippetsManager;
  $scope.subnets = SubnetsManager.getItems();
  $scope.machines = MachinesManager.getItems();
  $scope.devices = DevicesManager.getItems();
  $scope.controllers = ControllersManager.getItems();
  $scope.newSnippet = null;
  $scope.editSnippet = null;
  $scope.deleteSnippet = null;
  $scope.snippetTypes = ["Global", "Subnet", "Node"];
  $scope.MAAS_VERSION_NUMBER = DHCPSnippetsManager.formatMAASVersionNumber();

  // Return the text for the type of snippet.
  $scope.getSnippetTypeText = snippet => {
    if (angular.isString(snippet.node)) {
      return "Node";
    } else if (angular.isNumber(snippet.subnet)) {
      return "Subnet";
    } else {
      return "Global";
    }
  };

  // Return the node from either the machines, devices, or controllers manager.
  $scope.getNode = system_id => {
    let node = MachinesManager.getItemFromList(system_id);
    if (angular.isObject(node)) {
      return node;
    }
    node = DevicesManager.getItemFromList(system_id);
    if (angular.isObject(node)) {
      return node;
    }
    node = ControllersManager.getItemFromList(system_id);
    if (angular.isObject(node)) {
      return node;
    }
  };

  // Return the object the snippet applies to.
  $scope.getSnippetAppliesToObject = snippet => {
    if (angular.isString(snippet.node)) {
      return $scope.getNode(snippet.node);
    } else if (angular.isNumber(snippet.subnet)) {
      return SubnetsManager.getItemFromList(snippet.subnet);
    }
  };

  // Return the applies to text that is disabled in none edit mode.
  $scope.getSnippetAppliesToText = snippet => {
    let obj = $scope.getSnippetAppliesToObject(snippet);
    if (angular.isString(snippet.node) && angular.isObject(obj)) {
      return obj.fqdn;
    } else if (angular.isNumber(snippet.subnet) && angular.isObject(obj)) {
      return SubnetsManager.getName(obj);
    } else {
      return "";
    }
  };

  // Called when the active toggle is changed.
  $scope.snippetToggle = snippet => {
    DHCPSnippetsManager.updateItem(snippet).then(null, error => {
      // Revert state change and clear toggling.
      snippet.enabled = !snippet.enabled;
      $log.error(error);
    });
  };

  // Called to enter edit mode for a DHCP snippet.
  $scope.snippetEnterEdit = snippet => {
    $scope.newSnippet = null;
    $scope.deleteSnippet = null;
    $scope.editSnippet = snippet;
    $scope.editSnippet.type = $scope.getSnippetTypeText(snippet);
  };

  // Called to exit edit mode for a DHCP snippet.
  $scope.snippetExitEdit = () => {
    $scope.editSnippet = null;
  };

  // Return the name of the subnet.
  $scope.getSubnetName = subnet => {
    return SubnetsManager.getName(subnet);
  };

  // Called to exit remove mode for a DHCP snippet.
  $scope.snippetExitRemove = () => {
    $scope.deleteSnippet = null;
  };

  // Called to confirm the removal of a snippet.
  $scope.snippetConfirmRemove = () => {
    DHCPSnippetsManager.deleteItem($scope.deleteSnippet).then(() => {
      $scope.snippetExitRemove();
    });
  };

  // Called to enter remove mode for a DHCP snippet.
  $scope.snippetEnterRemove = snippet => {
    $scope.newSnippet = null;
    $scope.editSnippet = null;
    $scope.deleteSnippet = snippet;
  };

  // Called to cancel addind a new snippet.
  $scope.snippetAddCancel = () => {
    $scope.newSnippet = null;
  };

  // Called to start adding a new snippet.
  $scope.snippetAdd = () => {
    $scope.editSnippet = null;
    $scope.deleteSnippet = null;
    $scope.newSnippet = {
      name: "",
      type: "Global",
      enabled: true
    };
  };
}

export default maasDhcpSnippetsTable;
