import { ScriptStatus } from "../enum";

/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Results Controller
 */

/* @ngInject */
function NodeResultsController(
  $scope,
  $routeParams,
  $location,
  MachinesManager,
  ControllersManager,
  NodeResultsManagerFactory,
  ManagerHelperService,
  ErrorService
) {
  // NodeResultsManager that is loaded once the node is loaded.
  $scope.nodeResultsManager = null;
  // References to manager data used in scope.
  $scope.commissioning_results = null;
  $scope.testing_results = null;
  $scope.installation_results = null;
  $scope.results = null;

  // List of logs available.
  $scope.logs = {
    option: null,
    availableOptions: []
  };
  // Log content being displayed.
  $scope.logOutput = "Loading...";

  // Initial values.
  $scope.loaded = false;
  $scope.resultsLoaded = false;
  $scope.node = null;

  function updateLogs() {
    var i;
    var had_installation = $scope.logs.availableOptions.length === 3;
    $scope.logs.availableOptions.length = 0;
    // XXX ltrager 2017-12-01 - Only show the current installation log
    // if the machine is deploying, deployed, or failed deploying. The
    // logs page needs to be redesigned to show previous installation
    // results.
    if (
      $scope.installation_results &&
      $scope.installation_results.length > 0 &&
      ($scope.node.status_code === 6 ||
        $scope.node.status_code === 9 ||
        $scope.node.status_code === 11)
    ) {
      // If installation fails Curtin uploads a tar file of logs, the
      // UI needs to display the text log file, not the tar.
      for (i = 0; i < $scope.installation_results.length; i++) {
        if ($scope.installation_results[i].name === "/tmp/install.log") {
          $scope.logs.availableOptions.push({
            title: "Installation output",
            id: $scope.installation_results[i].id
          });
          break;
        }
      }
    }
    $scope.logs.availableOptions.push({
      title: "Machine output (YAML)",
      id: "summary_yaml"
    });
    $scope.logs.availableOptions.push({
      title: "Machine output (XML)",
      id: "summary_xml"
    });
    if (!had_installation && $scope.logs.availableOptions.length === 3) {
      // A new installation log has appeared, show it.
      $scope.logs.option = $scope.logs.availableOptions[0];
    } else if (
      !$scope.selectedLog ||
      (had_installation && $scope.logs.length === 2)
    ) {
      // No longer in a deployed state.
      $scope.logs.option = $scope.logs.availableOptions[0];
    }
  }

  // Called once the node has loaded.
  function nodeLoaded(node) {
    $scope.node = node;
    $scope.loaded = true;
    // Get the NodeResultsManager and load it.
    $scope.nodeResultsManager = NodeResultsManagerFactory.getManager(
      node,
      $scope.section.area
    );
    $scope.nodeResultsManager.loadItems().then(function() {
      $scope.commissioning_results =
        $scope.nodeResultsManager.commissioning_results;
      $scope.testing_results = $scope.nodeResultsManager.testing_results;
      $scope.installation_results =
        $scope.nodeResultsManager.installation_results;
      $scope.results = $scope.nodeResultsManager.results;
      // Only load and monitor logs when on the logs page.
      if ($scope.section.area === "logs") {
        updateLogs();
        $scope.$watch("installation_results", updateLogs, true);
        $scope.$watch("installation_results", $scope.updateLogOutput, true);
      }
      $scope.resultsLoaded = true;
    });
  }

  if ($location.path().indexOf("/controller") !== -1) {
    $scope.nodesManager = ControllersManager;
  } else {
    $scope.nodesManager = MachinesManager;
  }
  // Load nodes manager.
  ManagerHelperService.loadManager($scope, $scope.nodesManager).then(
    function() {
      // If redirected from the NodeDetailsController then the node
      // will already be active. No need to set it active again.
      var activeNode = $scope.nodesManager.getActiveItem();
      if (
        angular.isObject(activeNode) &&
        activeNode.system_id === $routeParams.system_id
      ) {
        nodeLoaded(activeNode);
      } else {
        $scope.nodesManager.setActiveItem($routeParams.system_id).then(
          function(node) {
            nodeLoaded(node);
          },
          function(error) {
            ErrorService.raiseError(error);
          }
        );
      }
    }
  );

  $scope.updateLogOutput = function() {
    $scope.logOutput = "Loading...";
    if (!$scope.node) {
      return;
    } else if ($scope.logs.option.id === "summary_xml") {
      $scope.nodesManager.getSummaryXML($scope.node).then(function(output) {
        $scope.logOutput = output;
      });
    } else if ($scope.logs.option.id === "summary_yaml") {
      $scope.nodesManager.getSummaryYAML($scope.node).then(function(output) {
        $scope.logOutput = output;
      });
    } else {
      var result = null;
      var i;
      // Find the installation result to be displayed.
      for (i = 0; i < $scope.installation_results.length; i++) {
        if ($scope.installation_results[i].id === $scope.logs.option.id) {
          result = $scope.installation_results[i];
          break;
        }
      }
      if (result === null) {
        $scope.logOutput = "BUG: No installation result found.";
        return;
      }
      switch (result.status) {
        case 0:
          $scope.logOutput = "System is booting...";
          break;
        case 1:
          $scope.logOutput = "Installation has begun!";
          break;
        case 2:
          $scope.nodeResultsManager
            .get_result_data(result.id, "combined")
            .then(function(output) {
              if (output === "") {
                $scope.logOutput =
                  "Installation has succeeded but " + "no output was given.";
              } else {
                $scope.logOutput = output;
              }
            });
          break;
        case 3:
          $scope.nodeResultsManager
            .get_result_data(result.id, "combined")
            .then(function(output) {
              if (output === "") {
                $scope.logOutput =
                  "Installation has failed and no " + "output was given.";
              } else {
                $scope.logOutput = output;
              }
            });
          break;
        case 4:
          $scope.logOutput = "Installation failed after 40 minutes.";
          break;
        case 5:
          $scope.logOutput = "Installation was aborted.";
          break;
        default:
          $scope.logOutput = "BUG: Unknown log status " + result.status;
          break;
      }
    }
  };

  $scope.loadHistory = function(result) {
    result.showing_results = false;
    // History has already been loaded, no need to request it.
    if (angular.isArray(result.history_list)) {
      result.showing_history = true;
      return;
    }
    result.loading_history = true;
    $scope.nodeResultsManager.get_history(result.id).then(function(history) {
      result.history_list = history;
      result.loading_history = false;
      result.showing_history = true;
    });
  };

  $scope.hasSuppressedTests = () => {
    return $scope.results.some(type => {
      const entries = Object.entries(type.results);
      return entries.some(entry => entry[1].some(result => result.suppressed));
    });
  };

  $scope.isSuppressible = result =>
    result.status === ScriptStatus.FAILED ||
    result.status === ScriptStatus.FAILED_INSTALLING ||
    result.status === ScriptStatus.TIMEDOUT ||
    result.status === ScriptStatus.FAILED_APPLYING_NETCONF;

  $scope.getSuppressedCount = () => {
    const suppressibleTests = $scope.results.reduce((acc, type) => {
      const entries = Object.entries(type.results);
      entries.forEach(entry => {
        entry[1].forEach(result => {
          if ($scope.isSuppressible(result)) {
            acc.push(result);
          }
        });
      });
      return acc;
    }, []);
    const suppressedTests = suppressibleTests.filter(test => test.suppressed);

    if (suppressibleTests.length === suppressedTests.length) {
      return "All";
    }
    return suppressedTests.length;
  };

  $scope.toggleSuppressed = result => {
    if (result.suppressed) {
      $scope.nodesManager.unsuppressTests($scope.node, [result]);
    } else {
      $scope.nodesManager.suppressTests($scope.node, [result]);
    }
  };

  // Destroy the NodeResultsManager when the scope is destroyed. This is
  // so the client will not recieve any more notifications about results
  // from this node.
  $scope.$on("$destroy", function() {
    if (angular.isObject($scope.nodeResultsManager)) {
      $scope.nodeResultsManager.destroy();
    }
  });
}

export default NodeResultsController;
