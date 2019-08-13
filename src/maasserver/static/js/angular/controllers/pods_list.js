/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Pods List Controller
 */

/* @ngInject */
function PodsListController(
  $scope,
  $rootScope,
  $location,
  PodsManager,
  UsersManager,
  GeneralManager,
  ZonesManager,
  ManagerHelperService,
  ResourcePoolsManager
) {
  // Checks if on RSD page
  $scope.onRSDSection = PodsManager.onRSDSection;

  // Set initial values.
  $scope.podManager = PodsManager;
  $scope.pods = PodsManager.getItems();
  $scope.loading = true;

  if ($scope.onRSDSection()) {
    $rootScope.title = "RSD";
    $rootScope.page = "rsd";
  } else {
    $rootScope.title = "KVM";
    $rootScope.page = "kvm";
  }

  $scope.filteredItems = [];
  $scope.selectedItems = PodsManager.getSelectedItems();
  $scope.predicate = "name";
  $scope.allViewableChecked = false;
  $scope.action = {
    option: null,
    options: [
      {
        name: "refresh",
        title: "Refresh",
        sentence: "refresh",
        operation: angular.bind(PodsManager, PodsManager.refresh)
      },
      {
        name: "delete",
        title: "Delete",
        sentence: "delete",
        operation: angular.bind(PodsManager, PodsManager.deleteItem)
      }
    ],
    progress: {
      total: 0,
      completed: 0,
      errors: 0
    }
  };
  $scope.add = {
    open: false,
    obj: {
      cpu_over_commit_ratio: 1,
      memory_over_commit_ratio: 1
    }
  };
  $scope.powerTypes = GeneralManager.getData("power_types");
  $scope.zones = ZonesManager.getItems();
  $scope.pools = ResourcePoolsManager.getItems();

  // Called to update `allViewableChecked`.
  function updateAllViewableChecked() {
    const pods = $scope.filterPods($scope.pods);

    // Not checked when no pods.
    if (pods.length === 0) {
      $scope.allViewableChecked = false;
      return;
    }

    // Loop through all filtered pods and see if all are checked.
    var i;
    for (i = 0; i < pods.length; i++) {
      if (!pods[i].$selected) {
        $scope.allViewableChecked = false;
        return;
      }
    }
    $scope.allViewableChecked = true;
  }

  function clearAction() {
    resetActionProgress();
    $scope.action.option = null;
  }

  // Clear the action if required.
  function shouldClearAction() {
    if ($scope.selectedItems.length === 0) {
      clearAction();
      if ($scope.action.option) {
        $scope.action.option = null;
      }
    }
  }

  // Reset actionProgress to zero.
  function resetActionProgress() {
    var progress = $scope.action.progress;
    progress.completed = progress.total = progress.errors = 0;
    angular.forEach($scope.pods, function(pod) {
      delete pod.action_failed;
    });
  }

  // After an action has been performed check if we can leave all pods
  // selected or if an error occurred and we should only show the failed
  // pods.
  function updateSelectedItems() {
    if (!$scope.hasActionsFailed()) {
      if (!$scope.hasActionsInProgress()) {
        clearAction();
      }
      return;
    }
    angular.forEach($scope.pods, function(pod) {
      if (pod.action_failed === false) {
        PodsManager.unselectItem(pod.id);
      }
    });
    shouldClearAction();
  }

  // Mark a pod as selected or unselected.
  $scope.toggleChecked = function(pod) {
    if (PodsManager.isSelected(pod.id)) {
      PodsManager.unselectItem(pod.id);
    } else {
      PodsManager.selectItem(pod.id);
    }
    updateAllViewableChecked();
    shouldClearAction();
  };

  // Select all viewable pods or deselect all viewable pods.
  $scope.toggleCheckAll = function() {
    const pods = $scope.filterPods($scope.pods);

    if ($scope.allViewableChecked) {
      angular.forEach(pods, function(pod) {
        PodsManager.unselectItem(pod.id);
      });
    } else {
      angular.forEach(pods, function(pod) {
        PodsManager.selectItem(pod.id);
      });
    }
    updateAllViewableChecked();
    shouldClearAction();
  };

  // When the pods change update if all check buttons should be
  // checked or not.
  $scope.$watchCollection("pods", function() {
    updateAllViewableChecked();
  });

  // Sorts the table by predicate.
  $scope.sortTable = function(predicate) {
    $scope.predicate = predicate;
    $scope.reverse = !$scope.reverse;
  };

  // Called when the current action is cancelled.
  $scope.actionCancel = function() {
    resetActionProgress();
    $scope.action.option = null;
  };

  // Calculate the available cores with overcommit applied
  $scope.availableWithOvercommit = PodsManager.availableWithOvercommit;

  // Perform the action on selected pods
  $scope.performAction = (pod, operation) => {
    operation(pod)
      .then(() => {
        $scope.action.progress.completed += 1;
        pod.action_failed = false;
        updateSelectedItems();
      })
      .catch(error => {
        $scope.action.progress.errors += 1;
        pod.action_error = error;
        pod.action_failed = true;
        updateSelectedItems();
      });
  };

  // Setup the action on selected pods
  $scope.actionGo = () => {
    let podToAction;

    if ($scope.action.option.isSingle) {
      podToAction = $scope.podToAction;
    }

    // Setup actionProgress.
    resetActionProgress();
    $scope.action.progress.total = $scope.selectedItems.length;

    let operation = $scope.action.option.operation;

    if (podToAction) {
      $scope.performAction(podToAction, operation);
    } else {
      $scope.selectedItems.forEach(pod => {
        $scope.performAction(pod, operation);
      });
    }
  };

  // Returns true when actions are being performed.
  $scope.hasActionsInProgress = function() {
    var progress = $scope.action.progress;
    return (
      progress.total > 0 &&
      progress.completed + progress.errors !== progress.total
    );
  };

  // Returns true if any of the actions have failed.
  $scope.hasActionsFailed = function() {
    var progress = $scope.action.progress;
    return progress.errors > 0;
  };

  // Called when the add pod button is pressed.
  $scope.addPod = function() {
    $scope.add.open = true;
    $scope.add.obj.zone = ZonesManager.getDefaultZone().id;
    $scope.add.obj.default_pool = ResourcePoolsManager.getDefaultPool().id;
    $scope.add.obj.cpu_over_commit_ratio = 1;
    $scope.add.obj.memory_over_commit_ratio = 1;

    if ($scope.onRSDSection()) {
      $scope.add.obj.type = "rsd";
    } else {
      $scope.add.obj.type = "virsh";
    }
  };

  // Called when the cancel add pod button is pressed.
  $scope.cancelAddPod = function() {
    $scope.add.open = false;
    $scope.add.obj = {};
  };

  // Return true if at least a rack controller is connected to the
  // region controller.
  $scope.isRackControllerConnected = function() {
    // If powerTypes exist then a rack controller is connected.
    return $scope.powerTypes.length > 0;
  };

  // Return true when the add pod buttons can be clicked.
  $scope.canAddPod = function() {
    return (
      $scope.isRackControllerConnected() &&
      UsersManager.hasGlobalPermission("pod_create")
    );
  };

  // Return true if the actions should be shown.
  $scope.showActions = function() {
    for (var i = 0; i < $scope.pods.length; i++) {
      if (
        $scope.pods[i].permissions &&
        $scope.pods[i].permissions.indexOf("edit") >= 0
      ) {
        return true;
      }
    }
    return false;
  };

  // Return the title of the power type.
  $scope.getPowerTypeTitle = function(power_type) {
    var i;
    for (i = 0; i < $scope.powerTypes.length; i++) {
      var powerType = $scope.powerTypes[i];
      if (powerType.name === power_type) {
        return powerType.description;
      }
    }
    return power_type;
  };

  // Filter pods depending on if page is rsd
  $scope.filterPods = function(pods) {
    return pods.filter(function(pod) {
      if ($scope.onRSDSection()) {
        return pod.type === "rsd";
      } else {
        return pod.type !== "rsd";
      }
    });
  };

  // Get page heading
  $scope.getPageHeading = function() {
    if ($scope.onRSDSection()) {
      return "RSD";
    } else {
      return "KVM";
    }
  };

  // Get route for details page
  $scope.getDetailsRoute = function() {
    if ($scope.onRSDSection()) {
      return "rsd";
    } else {
      return "kvm";
    }
  };

  // Get default pool data
  $scope.getDefaultPoolData = function(pod) {
    if (angular.isUndefined(pod) || !angular.isObject(pod)) {
      return;
    }

    if (angular.isUndefined(pod.storage_pools)) {
      return;
    }

    return pod.storage_pools.find(function(pool) {
      return pool.id === pod.default_storage_pool;
    });
  };

  // Get total network disk size
  $scope.getTotalNetworkDiskSize = function(pod) {
    if (angular.isUndefined(pod) || !angular.isObject(pod)) {
      return;
    }

    if (angular.isUndefined(pod.storage_pools)) {
      return;
    }

    var totalNetworkSize = 0;
    var networkPools = pod.storage_pools.filter(function(pool) {
      return pool.id !== pod.default_storage_pool;
    });

    networkPools.forEach(function(pool) {
      totalNetworkSize += pool.total;
    });

    return totalNetworkSize;
  };

  $scope.getMeterValue = function(total, value) {
    if (
      !angular.isNumber(total) ||
      angular.isUndefined(total) ||
      !angular.isNumber(value) ||
      angular.isUndefined(value)
    ) {
      return;
    }

    var minPercentage = 3;
    var valuePercentage = Math.round((value / total) * 100);

    if (valuePercentage < minPercentage && valuePercentage > 0) {
      return Math.round((total / 100) * minPercentage);
    } else {
      return value;
    }
  };

  $scope.handleMachineAction = (pod, type) => {
    if (
      angular.isUndefined(pod) ||
      angular.isUndefined(type) ||
      !angular.isObject(pod) ||
      !angular.isString(type)
    ) {
      return;
    }

    let action = $scope.action.options.find(option => option.name === type);
    action.isSingle = true;

    $scope.podToAction = pod;

    $scope.action.option = action;
  };

  $scope.getItemName = (itemId, items) => {
    if (
      angular.isUndefined(itemId) ||
      !angular.isNumber(itemId) ||
      angular.isUndefined(items) ||
      !angular.isArray(items)
    ) {
      return;
    }

    return items.find(item => item.id === itemId).name;
  };

  // Load the required managers for this controller.
  ManagerHelperService.loadManagers($scope, [
    PodsManager,
    UsersManager,
    GeneralManager,
    ZonesManager,
    ResourcePoolsManager
  ]).then(function() {
    // Deselct all pods/rsd on route change
    // otherwise you can perform actions on pods from rsd page
    // or actions on rsd from pods page
    $rootScope.$on("$routeChangeStart", () => {
      angular.forEach($scope.pods, pod => PodsManager.unselectItem(pod.id));
      $scope.allViewableChecked = false;
    });

    if ($location.search().addItem) {
      $scope.addPod();
    }
    $scope.pods.forEach(function(pod) {
      pod.default_pool_data = $scope.getDefaultPoolData(pod);
    });
    $scope.loading = false;

    // Set flag for RSD navigation item.
    if (!$rootScope.showRSDLink) {
      GeneralManager.getNavigationOptions().then(
        res => ($rootScope.showRSDLink = res.rsd)
      );
    }
  });
}

export default PodsListController;
