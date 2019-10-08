/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes List Controller
 */

/* @ngInject */
function NodesListController(
  $q,
  $scope,
  $interval,
  $rootScope,
  $routeParams,
  $route,
  $location,
  $window,
  $log,
  MachinesManager,
  DevicesManager,
  ControllersManager,
  GeneralManager,
  ManagerHelperService,
  SearchService,
  ZonesManager,
  UsersManager,
  ServicesManager,
  ScriptsManager,
  SwitchesManager,
  ResourcePoolsManager,
  VLANsManager,
  TagsManager,
  NotificationsManager
) {
  // Mapping of device.ip_assignment to viewable text.
  var DEVICE_IP_ASSIGNMENT = {
    external: "External",
    dynamic: "Dynamic",
    static: "Static"
  };

  // Set title and page.
  $rootScope.title = "Machines";
  $rootScope.page = "machines";

  // Set initial values.
  $scope.MAAS_config = $window.MAAS_config;
  $scope.machines = MachinesManager.getItems();
  $scope.zones = ZonesManager.getItems();
  $scope.pools = ResourcePoolsManager.getItems();
  $scope.devices = DevicesManager.getItems();
  $scope.controllers = ControllersManager.getItems();
  $scope.switches = SwitchesManager.getItems();
  $scope.showswitches = $routeParams.switches === "on";
  $scope.currentpage = "machines";
  $scope.osinfo = {};
  $scope.scripts = ScriptsManager.getItems();
  $scope.vlans = VLANsManager.getItems();
  $scope.loading = true;
  $scope.tags = [];
  $scope.failedActionSentence = "Action cannot be performed.";

  // Called for autocomplete when the user is typing a tag name.
  $scope.tagsAutocomplete = function(query) {
    return TagsManager.autocomplete(query);
  };

  $scope.tabs = {};
  $scope.pluralize = function(tab) {
    var singulars = {
      machines: "machine",
      switches: "switch",
      devices: "device",
      controllers: "controller"
    };
    var verb = singulars[tab];
    if ($scope.tabs[tab].selectedItems.length > 1) {
      verb = tab;
    }
    return verb;
  };
  // Machines tab.
  $scope.tabs.machines = {};
  $scope.tabs.machines.pagetitle = "Machines";
  $scope.tabs.machines.currentpage = "machines";
  $scope.tabs.machines.manager = MachinesManager;
  $scope.tabs.machines.previous_search = "";
  $scope.tabs.machines.search = "";
  $scope.tabs.machines.searchValid = true;
  $scope.tabs.machines.selectedItems = MachinesManager.getSelectedItems();
  $scope.tabs.machines.metadata = MachinesManager.getMetadata();
  $scope.tabs.machines.filters = SearchService.getEmptyFilter();
  $scope.tabs.machines.actionOption = null;
  $scope.tabs.machines.takeActionOptions = [];
  $scope.tabs.machines.actionErrorCount = 0;
  $scope.tabs.machines.actionProgress = {
    total: 0,
    completed: 0,
    errors: {},
    showing_confirmation: false,
    confirmation_message: "",
    confirmation_details: [],
    affected_nodes: 0
  };
  $scope.tabs.machines.osSelection = {
    osystem: null,
    release: null,
    hwe_kernel: null
  };
  $scope.tabs.machines.zoneSelection = null;
  $scope.tabs.machines.poolSelection = null;
  $scope.tabs.machines.poolAction = "select-pool";
  $scope.tabs.machines.newPool = {};
  $scope.tabs.machines.commissionOptions = {
    enableSSH: false,
    skipBMCConfig: false,
    skipNetworking: false,
    skipStorage: false,
    updateFirmware: false,
    configureHBA: false
  };
  $scope.tabs.machines.deployOptions = {
    installKVM: false
  };
  $scope.tabs.machines.releaseOptions = {};
  $scope.tabs.machines.commissioningSelection = [];
  $scope.tabs.machines.testSelection = [];
  $scope.tabs.machines.failedTests = [];
  $scope.tabs.machines.loadingFailedTests = false;
  $scope.tabs.machines.suppressFailedTestsChecked = false;
  $scope.tabs.machines.filterOrder = [
    "status",
    "owner",
    "pool",
    "architecture",
    "release",
    "tags",
    "storage_tags",
    "pod",
    "subnets",
    "fabrics",
    "zone"
  ];

  // Pools tab.
  $scope.tabs.pools = {};
  // The Pools tab is actually a sub tab of Machines.
  $scope.tabs.pools.pagetitle = "Machines";
  $scope.tabs.pools.currentpage = "pools";
  $scope.tabs.pools.manager = ResourcePoolsManager;
  $scope.tabs.pools.actionOption = false;
  $scope.tabs.pools.newPool = { name: null, description: null };
  $scope.tabs.pools.addPool = function() {
    $scope.tabs.pools.actionOption = true;
  };
  $scope.tabs.pools.cancelAddPool = function() {
    $scope.tabs.pools.actionOption = false;
    $scope.tabs.pools.newPool = {};
  };
  $scope.tabs.pools.activeTarget = null;
  $scope.tabs.pools.activeTargetAction = null;
  $scope.tabs.pools.actionErrorMessage = null;
  $scope.tabs.pools.initiatePoolAction = function(pool, action) {
    let tab = $scope.tabs.pools;
    // reset state in case of switching between deletes
    tab.cancelPoolAction();
    tab.activeTargetAction = action;
    tab.activeTarget = pool;
    tab.editingPool = pool; // used by maas-obj-form for editing
  };
  $scope.tabs.pools.cancelPoolAction = function() {
    let tab = $scope.tabs.pools;
    tab.activeTargetAction = null;
    tab.activeTarget = null;
    tab.actionErrorMessage = null;
  };
  $scope.tabs.pools.isPoolAction = function(pool, action) {
    let tab = $scope.tabs.pools;
    return (
      (angular.isUndefined(action) || tab.activeTargetAction === action) &&
      tab.activeTarget !== null &&
      tab.activeTarget.id === pool.id
    );
  };
  $scope.tabs.pools.actionConfirmEditPool = function() {
    $scope.tabs.pools.cancelPoolAction();
  };
  $scope.tabs.pools.actionConfirmDeletePool = function() {
    let tab = $scope.tabs.pools;
    tab.manager
      .deleteItem(tab.activeTarget)
      .then(tab.cancelPoolAction, function(error) {
        $scope.tabs.pools.actionErrorMessage = error;
      });
  };
  $scope.tabs.pools.goToPoolMachines = function(pool) {
    $scope.clearSearch("machines");
    $scope.toggleFilter("pool", pool.name, "machines");
    $scope.toggleTab("machines");
    // update the location URL otherwise to match the tab
    $location.path("/machines");
  };
  $scope.tabs.pools.isDefaultPool = function(pool) {
    return pool.id === 0;
  };

  $scope.nodesManager = MachinesManager;

  // Device tab.
  $scope.tabs.devices = {};
  $scope.tabs.devices.pagetitle = "Devices";
  $scope.tabs.devices.currentpage = "devices";
  $scope.tabs.devices.manager = DevicesManager;
  $scope.tabs.devices.previous_search = "";
  $scope.tabs.devices.search = "";
  $scope.tabs.devices.searchValid = true;
  $scope.tabs.devices.selectedItems = DevicesManager.getSelectedItems();
  $scope.tabs.devices.filtered_items = [];
  $scope.tabs.devices.predicate = "fqdn";
  $scope.tabs.devices.allViewableChecked = false;
  $scope.tabs.devices.metadata = DevicesManager.getMetadata();
  $scope.tabs.devices.filters = SearchService.getEmptyFilter();
  $scope.tabs.devices.column = "fqdn";
  $scope.tabs.devices.actionOption = null;
  $scope.tabs.devices.takeActionOptions = [];
  $scope.tabs.devices.actionErrorCount = 0;
  $scope.tabs.devices.actionProgress = {
    total: 0,
    completed: 0,
    errors: {},
    showing_confirmation: false,
    confirmation_message: "",
    confirmation_details: [],
    affected_nodes: 0
  };
  $scope.tabs.devices.zoneSelection = null;
  $scope.tabs.devices.poolSelection = null;
  $scope.tabs.devices.poolAction = "select-pool";
  $scope.tabs.devices.newPool = {};
  $scope.tabs.devices.filterOrder = ["owner", "tags", "zone"];

  // Controller tab.
  $scope.tabs.controllers = {};
  $scope.tabs.controllers.pagetitle = "Controllers";
  $scope.tabs.controllers.currentpage = "controllers";
  $scope.tabs.controllers.manager = ControllersManager;
  $scope.tabs.controllers.previous_search = "";
  $scope.tabs.controllers.search = "";
  $scope.tabs.controllers.searchValid = true;
  $scope.tabs.controllers.selectedItems = ControllersManager.getSelectedItems();
  $scope.tabs.controllers.filtered_items = [];
  $scope.tabs.controllers.predicate = "fqdn";
  $scope.tabs.controllers.allViewableChecked = false;
  $scope.tabs.controllers.metadata = ControllersManager.getMetadata();
  $scope.tabs.controllers.filters = SearchService.getEmptyFilter();
  $scope.tabs.controllers.column = "fqdn";
  $scope.tabs.controllers.actionOption = null;
  // Rack controllers contain all options
  $scope.tabs.controllers.takeActionOptions = [];
  $scope.tabs.controllers.actionErrorCount = 0;
  $scope.tabs.controllers.actionProgress = {
    total: 0,
    completed: 0,
    errors: {},
    showing_confirmation: false,
    confirmation_message: "",
    confirmation_details: [],
    affected_nodes: 0
  };
  $scope.tabs.controllers.zoneSelection = null;
  $scope.tabs.controllers.poolSelection = null;
  $scope.tabs.controllers.poolAction = "select-pool";
  $scope.tabs.controllers.newPool = {};
  $scope.tabs.controllers.syncStatuses = {};
  $scope.tabs.controllers.addController = false;
  $scope.tabs.controllers.registerUrl = $window.MAAS_config.register_url;
  $scope.tabs.controllers.registerSecret = $window.MAAS_config.register_secret;

  // Switch tab.
  $scope.tabs.switches = {};
  $scope.tabs.switches.pagetitle = "Switches";
  $scope.tabs.switches.currentpage = "switches";
  $scope.tabs.switches.manager = SwitchesManager;
  $scope.tabs.switches.previous_search = "";
  $scope.tabs.switches.search = "";
  $scope.tabs.switches.searchValid = true;
  $scope.tabs.switches.selectedItems = SwitchesManager.getSelectedItems();
  $scope.tabs.switches.predicate = "fqdn";
  $scope.tabs.switches.allViewableChecked = false;
  $scope.tabs.switches.metadata = SwitchesManager.getMetadata();
  $scope.tabs.switches.filters = SearchService.getEmptyFilter();
  $scope.tabs.switches.column = "fqdn";
  $scope.tabs.switches.actionOption = null;
  $scope.tabs.switches.takeActionOptions = [];
  $scope.tabs.switches.actionErrorCount = 0;
  $scope.tabs.switches.actionProgress = {
    total: 0,
    completed: 0,
    errors: {},
    showing_confirmation: false,
    confirmation_message: "",
    confirmation_details: [],
    affected_nodes: 0
  };
  $scope.tabs.switches.osSelection = {
    osystem: null,
    release: null,
    hwe_kernel: null
  };
  $scope.tabs.switches.zoneSelection = null;
  $scope.tabs.switches.poolSelection = null;
  $scope.tabs.switches.poolAction = "select-pool";
  $scope.tabs.switches.newPool = {};
  $scope.tabs.switches.commissioningSelection = [];
  $scope.tabs.switches.commissionOptions = {
    enableSSH: false,
    skipBMCConfig: false,
    skipNetworking: false,
    skipStorage: false,
    updateFirmware: false,
    configureHBA: false
  };
  $scope.tabs.switches.deployOptions = {
    installKVM: false
  };
  $scope.tabs.switches.releaseOptions = {};
  $scope.disableTestButton = false;

  // Options for add hardware dropdown.
  $scope.addHardwareOption = null;
  $scope.addHardwareOptions = [
    {
      name: "machine",
      title: "Machine"
    },
    {
      name: "chassis",
      title: "Chassis"
    },
    {
      name: "rsd",
      title: "RSD"
    }
  ];

  // This will hold the AddHardwareController once it is initialized.
  // The controller will set this variable as it's always a child of
  // this scope.
  $scope.addHardwareScope = null;

  // This will hold the AddDeviceController once it is initialized.
  // The controller will set this variable as it's always a child of
  // this scope.
  $scope.addDeviceScope = null;

  // When the addHardwareScope is hidden it will emit this event. We
  // clear the call to action button, so it can be used again.
  $scope.$on("addHardwareHidden", function() {
    $scope.addHardwareOption = null;
  });

  // Return true if the tab is in viewing selected mode.
  function isViewingSelected(tab) {
    var search = $scope.tabs[tab].search.toLowerCase();
    return search === "in:(selected)" || search === "in:selected";
  }

  // Sets the search bar to only show selected.
  function enterViewSelected(tab) {
    $scope.tabs[tab].previous_search = $scope.tabs[tab].search;
    $scope.tabs[tab].search = "in:(Selected)";
  }

  // Clear search bar from viewing selected.
  function leaveViewSelected(tab) {
    $scope.tabs.machines.suppressFailedTestsChecked = false;
    if (isViewingSelected(tab)) {
      $scope.tabs[tab].search = $scope.tabs[tab].previous_search;
      $scope.updateFilters(tab);
    }
  }

  // Called to update `allViewableChecked`.
  function updateAllViewableChecked(tab) {
    // Not checked when the filtered nodes are empty.
    if ($scope.tabs[tab].filtered_items.length === 0) {
      $scope.tabs[tab].allViewableChecked = false;
      return;
    }

    // Loop through all filtered nodes and see if all are checked.
    var i;
    for (i = 0; i < $scope.tabs[tab].filtered_items.length; i++) {
      if (!$scope.tabs[tab].filtered_items[i].$selected) {
        $scope.tabs[tab].allViewableChecked = false;
        return;
      }
    }
    $scope.tabs[tab].allViewableChecked = true;
  }

  function clearAction(tab) {
    resetActionProgress(tab);
    leaveViewSelected(tab);
    $scope.tabs[tab].actionOption = null;
    $scope.tabs[tab].zoneSelection = null;
    $scope.tabs[tab].poolSelection = null;
    $scope.tabs[tab].poolAction = "select-pool";
    $scope.tabs[tab].newPool = {};
    if (tab === "machines" || tab === "switches") {
      // Possible for this to be called before the osSelect
      // direction is initialized. In that case it has not
      // created the $reset function on the model object.
      if (angular.isFunction($scope.tabs[tab].osSelection.$reset)) {
        $scope.tabs[tab].osSelection.$reset();
      }
      $scope.tabs[tab].commissionOptions.enableSSH = false;
      $scope.tabs[tab].commissionOptions.skipBMCConfig = false;
      $scope.tabs[tab].commissionOptions.skipNetworking = false;
      $scope.tabs[tab].commissionOptions.skipStorage = false;
      $scope.tabs[tab].commissionOptions.updateFirmware = false;
      $scope.tabs[tab].commissionOptions.configureHBA = false;
      $scope.tabs[tab].deployOptions.installKVM = false;
    }
    $scope.tabs[tab].commissioningSelection = [];
    $scope.tabs[tab].testSelection = [];
  }

  // Clear the action if required.
  function shouldClearAction(tab) {
    if ($scope.tabs[tab].selectedItems.length === 0) {
      clearAction(tab);
    }
    if ($scope.tabs[tab].actionOption && !isViewingSelected(tab)) {
      $scope.tabs[tab].actionOption = null;
    }
  }

  // Called when the filtered_items are updated. Checks if the
  // filtered_items are empty and if the search still matches the
  // previous search. This will reset the search when no nodes match
  // the current filter.
  function removeEmptyFilter(tab) {
    if (
      $scope.tabs[tab].filtered_items.length === 0 &&
      $scope.tabs[tab].search !== "" &&
      $scope.tabs[tab].search === $scope.tabs[tab].previous_search
    ) {
      $scope.tabs[tab].search = "";
      $scope.updateFilters(tab);
    }
  }

  // Update the number of selected items which have an error based on the
  // current selected action.
  function updateActionErrorCount(tab) {
    var i;
    $scope.tabs[tab].actionErrorCount = 0;
    for (i = 0; i < $scope.tabs[tab].selectedItems.length; i++) {
      var supported = $scope.supportsAction(
        $scope.tabs[tab].selectedItems[i],
        tab
      );
      if (!supported) {
        $scope.tabs[tab].actionErrorCount += 1;
      }
      $scope.tabs[tab].selectedItems[i].action_failed = false;
    }
    $scope.updateFailedActionSentence(tab);
  }

  // Reset actionProgress on tab to zero.
  function resetActionProgress(tab) {
    var progress = $scope.tabs[tab].actionProgress;
    progress.completed = progress.total = 0;
    progress.errors = {};
    progress.showing_confirmation = false;
    progress.confirmation_message = "";
    progress.confirmation_details = [];
    progress.affected_nodes = 0;
  }

  // Add error to action progress and group error messages by nodes.
  function addErrorToActionProgress(tab, error, node) {
    var progress = $scope.tabs[tab].actionProgress;
    progress.completed += 1;
    var nodes = progress.errors[error];
    if (angular.isUndefined(nodes)) {
      progress.errors[error] = [node];
    } else {
      nodes.push(node);
    }
  }

  // After an action has been performed check if we can leave all nodes
  // selected or if an error occured and we should only show the failed
  // nodes.
  function updateSelectedItems(tab) {
    if (!$scope.hasActionsFailed(tab)) {
      if (!$scope.hasActionsInProgress(tab)) {
        clearAction(tab);
        enterViewSelected(tab);
      }
      return;
    }
    angular.forEach($scope.tabs[tab].manager.getItems(), function(node) {
      if (node.action_failed === false) {
        $scope.tabs[tab].manager.unselectItem(node.system_id);
      }
    });
  }

  $scope.setDefaultValues = parameters => {
    const keys = Object.keys(parameters);

    keys.forEach(key => {
      if (parameters[key].default) {
        parameters[key].value = parameters[key].default;
      }
    });

    return parameters;
  };

  $scope.checkTestParameterValues = () => {
    let disableButton = false;
    $scope.tabs.machines.testSelection.forEach(test => {
      const params = test.parameters;
      for (let key in params) {
        if (
          params[key].type === "url" &&
          !disableButton &&
          !params[key].value
        ) {
          disableButton = true;
        }
      }
    });

    $scope.disableTestButton = disableButton;
  };

  // Toggles between the current tab.
  $scope.toggleTab = function(tab) {
    $rootScope.title = $scope.tabs[tab].pagetitle;
    $rootScope.page = tab;
    $scope.currentpage = tab;

    switch (tab) {
      case "machines":
        $scope.osinfo = GeneralManager.getData("osinfo");
        $scope.tabs.machines.takeActionOptions = GeneralManager.getData(
          "machine_actions"
        );
        break;
      case "devices":
        $scope.tabs.devices.takeActionOptions = GeneralManager.getData(
          "device_actions"
        );
        break;
      case "controllers":
        $scope.tabs.controllers.takeActionOptions = GeneralManager.getData(
          "rack_controller_actions"
        );
        break;
      case "switches":
        // XXX: Which actions should there be?
        $scope.tabs.switches.takeActionOptions = GeneralManager.getData(
          "machine_actions"
        );
        break;
    }
  };

  // Clear the search bar.
  $scope.clearSearch = function(tab) {
    $scope.tabs[tab].search = "";
    $scope.updateFilters(tab);
  };

  // Mark a node as selected or unselected.
  $scope.toggleChecked = function(node, tab) {
    if (tab !== "machines" && tab !== "switches") {
      if ($scope.tabs[tab].manager.isSelected(node.system_id)) {
        $scope.tabs[tab].manager.unselectItem(node.system_id);
      } else {
        $scope.tabs[tab].manager.selectItem(node.system_id);
      }
      updateAllViewableChecked(tab);
    }

    updateActionErrorCount(tab);
    shouldClearAction(tab);
  };

  // Select all viewable nodes or deselect all viewable nodes.
  $scope.toggleCheckAll = function(tab) {
    if (tab !== "machines" && tab !== "switches") {
      if ($scope.tabs[tab].allViewableChecked) {
        angular.forEach($scope.tabs[tab].filtered_items, function(node) {
          $scope.tabs[tab].manager.unselectItem(node.system_id);
        });
      } else {
        angular.forEach($scope.tabs[tab].filtered_items, function(node) {
          $scope.tabs[tab].manager.selectItem(node.system_id);
        });
      }
      updateAllViewableChecked(tab);
    }
    updateActionErrorCount(tab);
    shouldClearAction(tab);
  };

  $scope.updateAvailableActions = function(tab) {
    var selectedNodes = $scope.tabs[tab].selectedItems;
    var actionOptions = $scope.tabs[tab].takeActionOptions;

    actionOptions.forEach(function(action) {
      var count = 0;
      selectedNodes.forEach(function(node) {
        if (node.actions.indexOf(action.name) > -1) {
          count += 1;
        }
        action.available = count;
      });
    });
  };

  $scope.unselectImpossibleNodes = tab => {
    const { actionOption, manager, selectedItems } = $scope.tabs[tab];

    const nodesToUnselect = selectedItems.reduce((acc, node) => {
      if (!node.actions.includes(actionOption.name)) {
        acc.push(node);
      }
      return acc;
    }, []);

    nodesToUnselect.forEach(node => {
      manager.unselectItem(node.system_id);
    });

    // 07/05/2019 Caleb: Force refresh of filtered machines.
    // Remove when machines table rewritten with one-way binding.
    $scope.tabs[tab].search = "in:(selected)";
  };

  $scope.onNodeListingChanged = function(nodes, tab) {
    if (
      nodes.length === 0 &&
      $scope.tabs[tab].search !== "" &&
      $scope.tabs[tab].search === $scope.tabs[tab].previous_search
    ) {
      $scope.tabs[tab].search = "";
      $scope.updateFilters(tab);
    }
  };

  // When the filtered nodes change update if all check buttons
  // should be checked or not.
  $scope.$watchCollection("tabs.devices.filtered_items", function() {
    updateAllViewableChecked("devices");
    removeEmptyFilter("devices");
  });
  $scope.$watchCollection("tabs.controllers.filtered_items", function() {
    updateAllViewableChecked("controllers");
    removeEmptyFilter("controllers");
  });

  // Shows the current selection.
  $scope.showSelected = function(tab) {
    enterViewSelected(tab);
    $scope.updateFilters(tab);
  };

  // Adds or removes a filter to the search.
  $scope.toggleFilter = function(type, value, tab) {
    // Don't allow a filter to be changed when an action is
    // in progress.
    if (angular.isObject($scope.tabs[tab].actionOption)) {
      return;
    }
    $scope.tabs[tab].filters = SearchService.toggleFilter(
      $scope.tabs[tab].filters,
      type,
      value,
      true
    );
    $scope.tabs[tab].search = SearchService.filtersToString(
      $scope.tabs[tab].filters
    );
  };

  // Return True if the filter is active.
  $scope.isFilterActive = function(type, value, tab) {
    return SearchService.isFilterActive(
      $scope.tabs[tab].filters,
      type,
      value,
      true
    );
  };

  // Update the filters object when the search bar is updated.
  $scope.updateFilters = function(tab) {
    var filters = SearchService.getCurrentFilters($scope.tabs[tab].search);
    if (filters === null) {
      $scope.tabs[tab].filters = SearchService.getEmptyFilter();
      $scope.tabs[tab].searchValid = false;
    } else {
      $scope.tabs[tab].filters = filters;
      $scope.tabs[tab].searchValid = true;
    }
    shouldClearAction(tab);
  };

  // Sorts the table by predicate.
  $scope.sortTable = function(predicate, tab) {
    $scope.tabs[tab].predicate = predicate;
    $scope.tabs[tab].reverse = !$scope.tabs[tab].reverse;
  };

  // Sets the viewable column or sorts.
  $scope.selectColumnOrSort = function(predicate, tab) {
    if ($scope.tabs[tab].column !== predicate) {
      $scope.tabs[tab].column = predicate;
    } else {
      $scope.sortTable(predicate, tab);
    }
  };

  // Return True if the node supports the action.
  $scope.supportsAction = function(node, tab) {
    if (!$scope.tabs[tab].actionOption) {
      return true;
    }
    return node.actions.indexOf($scope.tabs[tab].actionOption.name) >= 0;
  };

  $scope.getFailedTests = tabName => {
    const tab = $scope.tabs[tabName];
    const nodes = tab.selectedItems;
    tab.failedTests = [];
    tab.loadingFailedTests = true;
    MachinesManager.getLatestFailedTests(nodes).then(
      tests => {
        tab.failedTests = tests;
        tab.loadingFailedTests = false;
      },
      error => {
        const authUser = UsersManager.getAuthUser();
        if (angular.isObject(authUser)) {
          NotificationsManager.createItem({
            message: `Unable to load tests: ${error}`,
            category: "error",
            user: authUser.id
          });
        } else {
          $log.error(error);
        }
      }
    );
  };

  $scope.getFailedTestCount = tabName => {
    const tab = $scope.tabs[tabName];
    const nodes = tab.selectedItems;
    const tests = tab.failedTests;
    return nodes.reduce((acc, node) => {
      if (tests[node.system_id]) {
        acc += tests[node.system_id].length;
      }
      return acc;
    }, 0);
  };

  // Called when the action option gets changed.
  $scope.actionOptionSelected = function(tab) {
    updateActionErrorCount(tab);
    enterViewSelected(tab);

    // Hide the add hardware/device section.
    if (tab === "machines") {
      if (angular.isObject($scope.addHardwareScope)) {
        $scope.addHardwareScope.hide();
      }
    } else if (tab === "devices") {
      if (angular.isObject($scope.addDeviceScope)) {
        $scope.addDeviceScope.hide();
      }
    }

    if (
      $scope.tabs[tab].actionOption &&
      $scope.tabs[tab].actionOption.name === "override-failed-testing"
    ) {
      $scope.getFailedTests(tab);
    }
  };

  // Return True if there is an action error.
  $scope.isActionError = function(tab) {
    if (
      angular.isObject($scope.tabs[tab].actionOption) &&
      $scope.tabs[tab].actionOption.name === "deploy" &&
      $scope.tabs[tab].actionErrorCount === 0 &&
      $scope.osinfo.osystems.length === 0
    ) {
      return true;
    }
    return $scope.tabs[tab].actionErrorCount !== 0;
  };

  // Return True if unable to deploy because of missing images.
  $scope.isDeployError = function(tab) {
    if ($scope.tabs[tab].actionErrorCount !== 0) {
      return false;
    }
    if (
      angular.isObject($scope.tabs[tab].actionOption) &&
      $scope.tabs[tab].actionOption.name === "deploy" &&
      $scope.osinfo.osystems.length === 0
    ) {
      return true;
    }
    return false;
  };

  // Return True if deploy warning should be shown because of missing ssh keys.
  $scope.isSSHKeyWarning = function(tab) {
    if ($scope.tabs[tab].actionErrorCount !== 0) {
      return false;
    }
    if (
      angular.isObject($scope.tabs[tab].actionOption) &&
      $scope.tabs[tab].actionOption.name === "deploy" &&
      UsersManager.getSSHKeyCount() === 0
    ) {
      return true;
    }
    return false;
  };

  // Called when the current action is cancelled.
  $scope.actionCancel = function(tab) {
    resetActionProgress(tab);
    leaveViewSelected(tab);
    $scope.tabs[tab].actionOption = null;
    $scope.tabs[tab].suppressFailedTestsChecked = false;
    $scope.tabs[tab].testSelection.forEach(script => {
      script.parameters = $scope.setDefaultValues(script.parameters);
    });
  };

  // Perform the action on all nodes.
  $scope.actionGo = function(tabName) {
    var tab = $scope.tabs[tabName];
    var extra = {};
    let scriptInput = {};
    var deferred = $q.defer();
    // Actions can use preAction is to execute before the action
    // is exectued on all the nodes. We initialize it with a
    // promise so that later we can always treat it as a
    // promise, no matter if something is to be executed or not.
    var preAction = deferred.promise;
    deferred.resolve();
    var i, j;

    // Set deploy parameters if a deploy or set zone action.
    if (
      tab.actionOption.name === "deploy" &&
      angular.isString(tab.osSelection.osystem) &&
      angular.isString(tab.osSelection.release)
    ) {
      // Set extra. UI side the release is structured os/release, but
      // when it is sent over the websocket only the "release" is
      // sent.
      extra.osystem = tab.osSelection.osystem;
      var release = tab.osSelection.release;
      release = release.split("/");
      release = release[release.length - 1];
      extra.distro_series = release;
      // hwe_kernel is optional so only include it if its specified
      if (
        angular.isString(tab.osSelection.hwe_kernel) &&
        (tab.osSelection.hwe_kernel.indexOf("hwe-") >= 0 ||
          tab.osSelection.hwe_kernel.indexOf("ga-") >= 0)
      ) {
        extra.hwe_kernel = tab.osSelection.hwe_kernel;
      }
      let installKVM = tab.deployOptions.installKVM;
      // KVM pod deployment requires bionic.
      if (installKVM) {
        extra.osystem = "ubuntu";
        extra.distro_series = "bionic";
      }
      extra.install_kvm = installKVM;
    } else if (
      tab.actionOption.name === "set-zone" &&
      angular.isNumber(tab.zoneSelection.id)
    ) {
      // Set the zone parameter.
      extra.zone_id = tab.zoneSelection.id;
    } else if (tab.actionOption.name === "set-pool") {
      if (
        tab.poolAction === "create-pool" &&
        angular.isDefined(tab.newPool.name)
      ) {
        // Create the pool and set the action options with
        // the new pool id.
        preAction = ResourcePoolsManager.createItem({
          name: tab.newPool.name
        }).then(function(newPool) {
          extra.pool_id = newPool.id;
        });
      } else if (angular.isNumber(tab.poolSelection.id)) {
        // Set the pool parameter.
        extra.pool_id = tab.poolSelection.id;
      }
    } else if (tab.actionOption.name === "commission") {
      // Set the commission options.
      extra.enable_ssh = tab.commissionOptions.enableSSH;
      extra.skip_bmc_config = tab.commissionOptions.skipBMCConfig;
      extra.skip_networking = tab.commissionOptions.skipNetworking;
      extra.skip_storage = tab.commissionOptions.skipStorage;
      extra.commissioning_scripts = [];
      for (i = 0; i < tab.commissioningSelection.length; i++) {
        extra.commissioning_scripts.push(tab.commissioningSelection[i].id);
      }
      if (tab.commissionOptions.updateFirmware) {
        extra.commissioning_scripts.push("update_firmware");
      }
      if (tab.commissionOptions.configureHBA) {
        extra.commissioning_scripts.push("configure_hba");
      }
      if (extra.commissioning_scripts.length === 0) {
        // Tell the region not to run any custom commissioning
        // scripts.
        extra.commissioning_scripts.push("none");
      }
      extra.testing_scripts = [];
      for (i = 0; i < tab.testSelection.length; i++) {
        extra.testing_scripts.push(tab.testSelection[i].id);
      }
      if (extra.testing_scripts.length === 0) {
        // Tell the region not to run any tests.
        extra.testing_scripts.push("none");
      }
    } else if (tab.actionOption.name === "test") {
      if (!tab.actionProgress.showing_confirmation) {
        var progress = tab.actionProgress;
        for (i = 0; i < tab.selectedItems.length; i++) {
          if (tab.selectedItems[i].status_code === 6) {
            progress.affected_nodes++;
          }
        }
        if (progress.affected_nodes != 0) {
          progress.confirmation_message =
            progress.affected_nodes +
            " of " +
            tab.selectedItems.length +
            " " +
            $scope.page +
            " are in a deployed state.";
          progress.showing_confirmation = true;
          return;
        }
      }
      // Set the test options.
      extra.enable_ssh = tab.commissionOptions.enableSSH;
      extra.testing_scripts = [];
      for (i = 0; i < tab.testSelection.length; i++) {
        extra.testing_scripts.push(tab.testSelection[i].id);
      }
      if (extra.testing_scripts.length === 0) {
        // Tell the region not to run any tests.
        extra.testing_scripts.push("none");
      }
      const testingScriptsWithUrlParam = tab.testSelection.filter(test => {
        const paramsWithUrl = [];
        for (let key in test.parameters) {
          if (test.parameters[key].type === "url") {
            paramsWithUrl.push(test.parameters[key]);
          }
        }
        return paramsWithUrl.length;
      });

      testingScriptsWithUrlParam.forEach(test => {
        let urlValue;
        for (let key in test.parameters) {
          if (test.parameters[key].type === "url") {
            urlValue =
              test.parameters[key].value || test.parameters[key].default;
            break;
          }
        }
        scriptInput[test.name] = {
          url: urlValue
        };
      });

      extra.script_input = scriptInput;
    } else if (tab.actionOption.name === "release") {
      // Set the release options.
      extra.erase = tab.releaseOptions.erase;
      extra.secure_erase = tab.releaseOptions.secureErase;
      extra.quick_erase = tab.releaseOptions.quickErase;
    } else if (
      tab.actionOption.name === "delete" &&
      tabName === "controllers" &&
      !tab.actionProgress.showing_confirmation
    ) {
      for (i = 0; i < tab.selectedItems.length; i++) {
        var controller = tab.selectedItems[i];
        for (j = 0; j < $scope.vlans.length; j++) {
          var vlan = $scope.vlans[j];
          if (vlan.primary_rack === controller.system_id) {
            tab.actionProgress.confirmation_details.push(
              controller.fqdn +
                " is the primary rack controller for " +
                vlan.name
            );
            tab.actionProgress.affected_nodes++;
          }
          if (vlan.secondary_rack === controller.system_id) {
            tab.actionProgress.confirmation_details.push(
              controller.fqdn +
                " is the secondary rack controller for " +
                vlan.name
            );
            tab.actionProgress.affected_nodes++;
          }
        }
      }
      if (tab.actionProgress.affected_nodes != 0) {
        if (tab.actionProgress.affected_nodes === 1) {
          tab.actionProgress.confirmation_message =
            "1 controller will be deleted.";
        } else {
          tab.actionProgress.confirmation_message =
            tab.actionProgress.affected_nodes + " controllers will be deleted.";
        }
        tab.actionProgress.showing_confirmation = true;
        return;
      }
    } else if (tab.actionOption.name === "tag") {
      extra.tags = $scope.tags.map(function(tag) {
        return tag.text;
      });

      $scope.tags = [];
    } else if (
      tab.actionOption.name === "override-failed-testing" &&
      tab.suppressFailedTestsChecked
    ) {
      const nodes = tab.selectedItems;
      const tests = tab.failedTests;
      nodes.forEach(node => {
        if (tests[node.system_id]) {
          tab.manager.suppressTests(node, tests[node.system_id]);
        }
      });
      $scope.tabs.machines.suppressFailedTestsChecked = false;
    }

    preAction.then(
      function() {
        // Setup actionProgress.
        resetActionProgress(tabName);
        tab.actionProgress.total = tab.selectedItems.length;
        // Perform the action on all selected items.
        angular.forEach(tab.selectedItems, function(node) {
          tab.manager
            .performAction(node, tab.actionOption.name, extra)
            .then(
              function() {
                tab.actionProgress.completed += 1;
                node.action_failed = false;
              },
              function(error) {
                addErrorToActionProgress(tabName, error, node);
                node.action_failed = true;
                tab.testSelection.forEach(script => {
                  script.parameters = $scope.setDefaultValues(
                    script.parameters
                  );
                });
              }
            )
            .finally(function() {
              updateSelectedItems(tabName);
            });
        });
      },
      function(error) {
        addErrorToActionProgress(tabName, error);
      }
    );
  };

  // Returns true when actions are being performed.
  $scope.hasActionsInProgress = function(tab) {
    var progress = $scope.tabs[tab].actionProgress;
    return progress.total > 0 && progress.completed !== progress.total;
  };

  // Returns true if any of the actions have failed.
  $scope.hasActionsFailed = function(tab) {
    return Object.keys($scope.tabs[tab].actionProgress.errors).length > 0;
  };

  // Called to when the addHardwareOption has changed.
  $scope.addHardwareOptionChanged = function() {
    if ($scope.addHardwareOption) {
      if ($scope.addHardwareOption.name === "rsd") {
        $location.path("/rsd");
        $location.search("addItem", true);
        $route.reload();
      } else {
        $scope.addHardwareScope.show($scope.addHardwareOption.name);
      }
    }
  };

  // Called when the add device button is pressed.
  $scope.addDevice = function() {
    $scope.addDeviceScope.show();
  };

  // Called when the cancel add device button is pressed.
  $scope.cancelAddDevice = function() {
    $scope.addDeviceScope.cancel();
  };

  // Get the display text for device ip assignment type.
  $scope.getDeviceIPAssignment = function(ipAssignment) {
    return DEVICE_IP_ASSIGNMENT[ipAssignment];
  };

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Return true if the user can create a resource pool.
  $scope.canAddMachine = function() {
    return UsersManager.hasGlobalPermission("machine_create");
  };

  // Return true if the user can create a resource pool.
  $scope.canCreateResourcePool = function() {
    return UsersManager.hasGlobalPermission("resource_pool_create");
  };

  // Return true if the actions column should be shown.
  $scope.showResourcePoolActions = function() {
    for (var i = 0; i < $scope.pools.length; i++) {
      if (
        $scope.pools[i].permissions &&
        $scope.pools[i].permissions.length > 0
      ) {
        return true;
      }
    }
    return false;
  };

  // Return true if user can edit resource pool.
  $scope.canEditResourcePool = function(pool) {
    if (pool.permissions && pool.permissions.indexOf("edit") !== -1) {
      return true;
    }
    return false;
  };

  // Return true if user can delete resource pool.
  $scope.canDeleteResourcePool = function() {
    return UsersManager.hasGlobalPermission("resource_pool_delete");
  };

  // Return true if custom commissioning scripts exist.
  $scope.hasCustomCommissioningScripts = function() {
    var i;
    for (i = 0; i < $scope.scripts.length; i++) {
      if ($scope.scripts[i].script_type === 0) {
        return true;
      }
    }
    return false;
  };

  $scope.updateFailedActionSentence = tab => {
    const { actionOption, actionErrorCount } = $scope.tabs[tab];

    // e.g. "5 machines" or "1 controller"
    const nodeString =
      actionErrorCount > 1
        ? `${actionErrorCount} ${tab}`
        : `${actionErrorCount} ${tab.slice(0, -1)}`;
    let sentence = `Action cannot be performed on ${nodeString}.`;

    if (actionOption && actionOption.name) {
      switch (actionOption.name) {
        case "exit-rescue-mode":
          sentence = `${nodeString} cannot exit rescue mode.`;
          break;
        case "lock":
          sentence = `${nodeString} cannot be locked.`;
          break;
        case "override-failed-testing":
          sentence = `Cannot override failed tests on ${nodeString}.`;
          break;
        case "rescue-mode":
          sentence = `${nodeString} cannot be put in rescue mode.`;
          break;
        case "set-pool":
          sentence = `Cannot set pool of ${nodeString}.`;
          break;
        case "set-zone":
          sentence = `Cannot set zone of ${nodeString}.`;
          break;
        case "unlock":
          sentence = `${nodeString} cannot be unlocked.`;
          break;
        default:
          sentence = `${nodeString} cannot be ${actionOption.sentence}.`;
      }
    }

    $scope.failedActionSentence = sentence;
  };

  $scope.getHardwareTestErrorText = function(error, tab) {
    var selectedItemsCount = $scope.tabs[tab].selectedItems.length;

    if (error === "Unable to run destructive test while deployed!") {
      var singular = false;
      var machinesText = "";

      if (selectedItemsCount === 1) {
        singular = true;
      }

      if (singular) {
        machinesText += "1 machine";
      } else {
        machinesText += selectedItemsCount + " machines";
      }

      return (
        machinesText +
        " cannot run hardware testing. The selected hardware tests contain" +
        " one or more destructive tests. Destructive tests cannot run on" +
        " deployed machines."
      );
    } else {
      return error;
    }
  };

  // Reload osinfo when the page reloads
  $scope.$on("$routeUpdate", function() {
    GeneralManager.loadItems(["osinfo"]);
  });

  // Switch to the specified tab, if specified.
  angular.forEach(
    ["machines", "pools", "devices", "controllers", "switches"],
    function(node_type) {
      if ($location.path().indexOf("/" + node_type) !== -1) {
        $scope.toggleTab(node_type);
      }
    }
  );

  // The ScriptsManager is only needed for selecting testing or
  // commissioning scripts.
  var page_managers = [$scope.tabs[$scope.currentpage].manager];
  if (
    $scope.currentpage === "machines" ||
    $scope.currentpage === "controllers"
  ) {
    page_managers.push(ScriptsManager);
  }
  if ($scope.currentpage === "controllers") {
    // VLANsManager is used during controller delete to see if its
    // managing a VLAN when confirming delete.
    page_managers.push(VLANsManager);
  }

  // Load the required managers for this controller. The ServicesManager
  // is required by the maasControllerStatus directive that is used
  // in the partial for this controller.
  ManagerHelperService.loadManagers(
    $scope,
    page_managers.concat([
      GeneralManager,
      ZonesManager,
      UsersManager,
      ResourcePoolsManager,
      ServicesManager,
      TagsManager
    ])
  ).then(function() {
    $scope.loading = false;

    // Set flag for RSD navigation item.
    if (!$rootScope.showRSDLink) {
      GeneralManager.getNavigationOptions().then(
        res => ($rootScope.showRSDLink = res.rsd)
      );
    }
  });

  // Stop polling and save the current filter when the scope is destroyed.
  $scope.$on("$destroy", function() {
    $interval.cancel($scope.statusPoll);
    SearchService.storeFilters("machines", $scope.tabs.machines.filters);
    SearchService.storeFilters("devices", $scope.tabs.devices.filters);
    SearchService.storeFilters("controllers", $scope.tabs.controllers.filters);
    SearchService.storeFilters("switches", $scope.tabs.switches.filters);
  });

  // Restore the filters if any saved.
  var machinesFilter = SearchService.retrieveFilters("machines");
  if (angular.isObject(machinesFilter)) {
    $scope.tabs.machines.search = SearchService.filtersToString(machinesFilter);
    $scope.updateFilters("machines");
  }
  var devicesFilter = SearchService.retrieveFilters("devices");
  if (angular.isObject(devicesFilter)) {
    $scope.tabs.devices.search = SearchService.filtersToString(devicesFilter);
    $scope.updateFilters("devices");
  }
  var controllersFilter = SearchService.retrieveFilters("controllers");
  if (angular.isObject(controllersFilter)) {
    $scope.tabs.controllers.search = SearchService.filtersToString(
      controllersFilter
    );
    $scope.updateFilters("controllers");
  }
  var switchesFilter = SearchService.retrieveFilters("switches");
  if (angular.isObject(switchesFilter)) {
    $scope.tabs.switches.search = SearchService.filtersToString(switchesFilter);
    $scope.updateFilters("switches");
  }

  // Set the query if the present in $routeParams.
  var query = $routeParams.query;
  if (angular.isString(query)) {
    $scope.tabs[$scope.currentpage].search = query;
    $scope.updateFilters($scope.currentpage);
  }
}

export default NodesListController;
