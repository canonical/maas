/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Details Controller
 */

import { NodeTypes } from "../enum";

/* @ngInject */
function NodeDetailsController(
  $scope,
  $rootScope,
  $routeParams,
  $location,
  DevicesManager,
  MachinesManager,
  ControllersManager,
  ZonesManager,
  GeneralManager,
  UsersManager,
  TagsManager,
  DomainsManager,
  ManagerHelperService,
  ServicesManager,
  ErrorService,
  ValidationService,
  ScriptsManager,
  ResourcePoolsManager,
  VLANsManager,
  FabricsManager,
  $log,
  $window
) {
  // Mapping of device.ip_assignment to viewable text.
  var DEVICE_IP_ASSIGNMENT = {
    external: "External",
    dynamic: "Dynamic",
    static: "Static"
  };

  // Set title and page.
  $rootScope.title = "Loading...";

  // Initial values.
  $scope.MAAS_config = $window.MAAS_config;
  $scope.loaded = false;
  $scope.node = null;
  $scope.action = {
    option: null,
    allOptions: null,
    availableOptions: [],
    error: null,
    showing_confirmation: false,
    confirmation_message: "",
    confirmation_details: []
  };
  $scope.power_types = GeneralManager.getData("power_types");
  $scope.osinfo = GeneralManager.getData("osinfo");
  $scope.section = {
    area: angular.isString($routeParams.area) ? $routeParams.area : "summary"
  };
  $scope.osSelection = {
    osystem: null,
    release: null,
    hwe_kernel: null
  };
  $scope.commissionOptions = {
    enableSSH: false,
    skipBMCConfig: false,
    skipNetworking: false,
    skipStorage: false,
    updateFirmware: false,
    configureHBA: false
  };
  $scope.deployOptions = {
    installKVM: false
  };
  $scope.commissioningSelection = [];
  $scope.testSelection = [];
  $scope.releaseOptions = {};
  $scope.checkingPower = false;
  $scope.devices = [];
  $scope.fabrics = FabricsManager.getItems();
  $scope.scripts = ScriptsManager.getItems();
  $scope.vlans = VLANsManager.getItems();
  $scope.hideHighAvailabilityNotification = false;
  $scope.failedUpdateError = "";
  $scope.disableTestButton = false;
  $scope.numaDetails = [];
  $scope.expandedNumas = [];
  $scope.groupedInterfaces = [];

  // Node header section.
  $scope.header = {
    editing: false,
    editing_domain: false,
    hostname: {
      value: ""
    },
    domain: {
      selected: null,
      options: DomainsManager.getItems()
    }
  };

  // Summary section.
  $scope.summary = {
    editing: false,
    architecture: {
      selected: null,
      options: GeneralManager.getData("architectures")
    },
    min_hwe_kernel: {
      selected: null,
      options: GeneralManager.getData("min_hwe_kernels")
    },
    zone: {
      selected: null,
      options: ZonesManager.getItems()
    },
    pool: {
      selected: null,
      options: ResourcePoolsManager.getItems()
    },
    tags: []
  };

  // Service monitor section (for controllers).
  $scope.services = {};

  // Power section.
  $scope.power = {
    editing: false,
    type: null,
    bmc_node_count: 0,
    parameters: {},
    in_pod: false
  };

  // Dismiss high availability notification
  $scope.dismissHighAvailabilityNotification = function() {
    $scope.hideHighAvailabilityNotification = true;
    localStorage.setItem(
      `hideHighAvailabilityNotification-${$scope.vlan.id}`,
      true
    );
  };

  $scope.getNotificationVLANText = function() {
    if ($scope.node.vlan.name) {
      return $scope.node.vlan.name;
    } else {
      return $scope.node.vlan.id;
    }
  };

  $scope.showHighAvailabilityNotification = function() {
    if (
      !$scope.hideHighAvailabilityNotification &&
      $scope.node.dhcp_on &&
      $scope.vlan &&
      $scope.vlan.rack_sids.length > 1 &&
      !$scope.vlan.secondary_rack &&
      $scope.node.node_type !== NodeTypes.REGION_CONTROLLER
    ) {
      if (
        $scope.section.area === "summary" ||
        $scope.section.area === "vlans"
      ) {
        return true;
      }
    }

    return false;
  };

  // Get the display text for device ip assignment type.
  $scope.getDeviceIPAssignment = function(ipAssignment) {
    return DEVICE_IP_ASSIGNMENT[ipAssignment];
  };

  // Events section.
  $scope.events = {
    limit: 10
  };

  // Add parameters to URL so tab state persists
  $scope.openSection = function(sectionName) {
    $scope.section.area = sectionName;
    $location.search("area", sectionName);
  };

  $scope.checkTestParameterValues = () => {
    let disableButton = false;
    $scope.testSelection.forEach(test => {
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

  $scope.shallowCompare = (obj1, obj2) =>
    Object.keys(obj1).length === Object.keys(obj2).length &&
    Object.keys(obj1).every(key => obj1[key] === obj2[key]);

  $scope.groupInterfaces = interfaces => {
    const physicalInterfaces = interfaces.filter(
      iface => iface.type === "physical"
    );
    const sortedGroups = physicalInterfaces
      .reduce((acc, iface) => {
        const { vendor, product, firmware_version } = iface;
        const group = {
          vendor: vendor || "Unknown network card",
          product,
          firmware_version
        };
        if (!acc.some(item => $scope.shallowCompare(item, group))) {
          acc.push(group);
        }
        return acc;
      }, [])
      .sort((a, b) => {
        const vendorA = a.vendor.toUpperCase();
        const vendorB = b.vendor.toUpperCase();
        const productA = a.product && a.product.toUpperCase();
        const productB = b.product && b.product.toUpperCase();
        const versionA = a.firmware_version;
        const versionB = b.firmware_version;

        if (vendorA === "UNKNOWN NETWORK CARD") {
          return 1;
        }
        if (vendorB === "UNKNOWN NETWORK CARD") {
          return -1;
        }
        if (vendorA === vendorB) {
          if (productA === productB) {
            if (versionA === versionB) {
              return 0;
            }
            return versionA > versionB ? 1 : -1;
          }
          return productA > productB ? 1 : -1;
        }
        return vendorA > vendorB ? 1 : -1;
      });

    return sortedGroups.map(group => {
      const { vendor, product, firmware_version } = group;
      let groupIfaces = [];

      if (vendor === "Unknown network card") {
        groupIfaces = physicalInterfaces.filter(iface => !iface.vendor);
      } else {
        groupIfaces = physicalInterfaces.filter(iface => {
          return (
            iface.vendor === group.vendor &&
            iface.product === group.product &&
            iface.firmware_version === group.firmware_version
          );
        });
      }

      return {
        vendor,
        product,
        firmware_version,
        interfaces: groupIfaces
      };
    });
  };

  // Updates the page title.
  function updateTitle() {
    if ($scope.node && $scope.node.fqdn) {
      $rootScope.title = $scope.node.fqdn;
    }
  }

  function updateHeader() {
    // Don't update the value if in editing mode. As this would
    // overwrite the users changes.
    if ($scope.header.editing || $scope.header.editing_domain) {
      return;
    }
    $scope.header.hostname.value = $scope.node.fqdn;
    // DomainsManager gives us all Domain information while the node
    // only contains the name and id. Because of this we need to loop
    // through the DomainsManager options and find the option with the
    // id matching the node id. Otherwise we end up setting our
    // selected field to an option not from DomainsManager which
    // doesn't work.
    for (let i = 0; i < $scope.header.domain.options.length; i++) {
      let option = $scope.header.domain.options[i];
      if (option.id === $scope.node.domain.id) {
        $scope.header.domain.selected = option;
        break;
      }
    }
  }

  // Update the available action options for the node.
  function updateAvailableActionOptions() {
    if (!angular.isObject($scope.node)) {
      return;
    }
    const actionTypeForNodeType = {
      0: "machine_actions",
      1: "device_actions",
      2: "rack_controller_actions",
      3: "region_controller_actions",
      4: "region_and_rack_controller_actions"
    };
    if (
      GeneralManager.isDataLoaded(actionTypeForNodeType[$scope.node.node_type])
    ) {
      // Build the available action options control from the
      // allowed actions, except set-zone which does not make
      // sense in this view because the form has this
      // functionality
      $scope.action.allOptions = GeneralManager.getData(
        actionTypeForNodeType[$scope.node.node_type]
      );
      $scope.action.availableOptions.length = 0;
      angular.forEach($scope.action.allOptions, function(option) {
        if (
          $scope.node.actions.indexOf(option.name) >= 0 &&
          option.name !== "set-zone" &&
          option.name !== "set-pool" &&
          option.name !== "tag"
        ) {
          $scope.action.availableOptions.push(option);
        }
      });
    } else {
      // The GeneralManager only loads data requested on load. This
      // isn't called until after load as its triggered on the loaded
      // node's actions. If the node's action list isn't loaded load
      // it then update the available options.
      GeneralManager.loadItems([
        actionTypeForNodeType[$scope.node.node_type]
      ]).then(updateAvailableActionOptions);
    }
  }

  // Updates the currently selected items in the power section.
  function updatePower() {
    // Do not update the selected items, when editing this would
    // cause the users selection to change.
    if ($scope.power.editing) {
      return;
    }

    $scope.power.type = null;
    for (let i = 0; i < $scope.power_types.length; i++) {
      if ($scope.node.power_type === $scope.power_types[i].name) {
        $scope.power.type = $scope.power_types[i];
        break;
      }
    }

    $scope.power.bmc_node_count = $scope.node.power_bmc_node_count;

    $scope.power.parameters = angular.copy($scope.node.power_parameters);
    if (!angular.isObject($scope.power.parameters)) {
      $scope.power.parameters = {};
    }

    // Force editing mode on, if the power_type is missing for a
    // machine. This is placed at the bottom because we wanted the
    // selected items to be filled in at least once.
    if (
      $scope.canEdit() &&
      $scope.node.power_type === "" &&
      $scope.node.node_type === 0
    ) {
      $scope.power.editing = true;
    }

    $scope.power.in_pod = angular.isDefined($scope.node.pod);
  }

  // Updates the currently selected items in the summary section.
  const updateSummary = () => {
    const { node, summary } = $scope;
    // Do not update the selected items, when editing this would
    // cause the users selection to change.
    if (summary.editing) {
      return;
    }

    if (angular.isObject(node.zone)) {
      summary.zone.selected = ZonesManager.getItemFromList(node.zone.id);
    }
    if (angular.isObject(node.pool)) {
      summary.pool.selected = ResourcePoolsManager.getItemFromList(
        node.pool.id
      );
    }
    summary.architecture.selected = node.architecture;
    summary.description = node.description;
    summary.min_hwe_kernel.selected = node.min_hwe_kernel;
    summary.tags = angular.copy(node.tags);

    // Force editing mode on, if the architecture is invalid. This is
    // placed at the bottom because we wanted the selected items to
    // be filled in at least once.
    if (
      $scope.canEdit() &&
      $scope.hasUsableArchitectures() &&
      $scope.hasInvalidArchitecture()
    ) {
      summary.editing = true;
    }

    if (node.numa_nodes) {
      const numaDetails = node.numa_nodes.map(numa => {
        const numaDisks = node.disks
          ? node.disks.filter(disk => disk.numa_node === numa.index)
          : [];
        const numaInterfaces = node.interfaces
          ? node.interfaces.filter(iface => iface.numa_node === numa.index)
          : [];
        const storage = numaDisks.reduce((acc, disk) => acc + disk.size, 0);
        return {
          index: numa.index,
          cores: numa.cores,
          memory: numa.memory,
          storage,
          disks: numaDisks.length,
          network: numaInterfaces.length
        };
      });
      $scope.numaDetails = numaDetails;
    }

    if (node.interfaces) {
      $scope.groupedInterfaces = $scope.groupInterfaces(node.interfaces);
    }
  };

  // Updates the service monitor section.
  function updateServices() {
    if ($scope.isController) {
      $scope.services = {};
      angular.forEach(ControllersManager.getServices($scope.node), function(
        service
      ) {
        $scope.services[service.name] = service;
      });
    }
  }

  // Update the devices array on the scope based on the device children
  // on the node.
  function updateDevices() {
    $scope.devices = [];
    angular.forEach($scope.node.devices, function(child) {
      var device = {
        name: child.fqdn
      };

      // Add the interfaces to the device object if any exists.
      if (angular.isArray(child.interfaces) && child.interfaces.length > 0) {
        angular.forEach(child.interfaces, function(nic, nicIdx) {
          var deviceWithMAC = angular.copy(device);
          deviceWithMAC.mac_address = nic.mac_address;

          // Remove device name so it is not duplicated in the
          // table since this is another MAC address on this
          // device.
          if (nicIdx > 0) {
            deviceWithMAC.name = "";
          }

          // Add this links to the device object if any exists.
          if (angular.isArray(nic.links) && nic.links.length > 0) {
            angular.forEach(nic.links, function(link, lIdx) {
              var deviceWithLink = angular.copy(deviceWithMAC);
              deviceWithLink.ip_address = link.ip_address;

              // Remove the MAC address so it is not
              // duplicated in the table since this is
              // another link on this interface.
              if (lIdx > 0) {
                deviceWithLink.mac_address = "";
              }

              $scope.devices.push(deviceWithLink);
            });
          } else {
            $scope.devices.push(deviceWithMAC);
          }
        });
      } else {
        $scope.devices.push(device);
      }
    });
  }

  // Starts the watchers on the scope.
  function startWatching() {
    if (angular.isObject($scope.node)) {
      // Update the title and name when the node fqdn changes.
      $scope.$watch("node.fqdn", function() {
        updateTitle();
        updateHeader();
      });

      // Update the devices on the node.
      $scope.$watch("node.devices", updateDevices);

      // Update the availableActionOptions when the node actions change.
      $scope.$watch("node.actions", updateAvailableActionOptions);

      // Update the summary when the node or architectures list is
      // updated.
      $scope.$watch("node.architecture", updateSummary);
      $scope.$watchCollection(
        $scope.summary.architecture.options,
        updateSummary
      );

      // Uppdate the summary when min_hwe_kernel is updated.
      $scope.$watch("node.min_hwe_kernel", updateSummary);
      $scope.$watchCollection(
        $scope.summary.min_hwe_kernel.options,
        updateSummary
      );

      // Update the summary when the node or zone list is
      // updated.
      $scope.$watch("node.zone.id", updateSummary);
      $scope.$watchCollection($scope.summary.zone.options, updateSummary);

      // Update the summary when the node or the resouce pool list is
      // updated.
      $scope.$watch("node.pool.id", updateSummary);
      $scope.$watchCollection($scope.summary.pool.options, updateSummary);

      // Update the power when the node power_type or power_parameters
      // are updated.
      $scope.$watch("node.power_type", updatePower);
      $scope.$watch("node.power_parameters", updatePower);
      $scope.$watchCollection("power_types", updatePower);

      // Update the services when the services list is updated.
      $scope.$watch("node.service_ids", updateServices);
    }
  }

  // Called when the node has been loaded.
  function nodeLoaded(node) {
    $scope.node = node;
    $scope.loaded = true;

    updateTitle();
    updateSummary();
    updateServices();
    startWatching();

    // Tell the storageController and networkingController that the
    // node has been loaded.
    if (angular.isObject($scope.storageController)) {
      $scope.storageController.nodeLoaded();
    }
    if (angular.isObject($scope.networkingController)) {
      $scope.networkingController.nodeLoaded();
    }

    if (angular.isObject($scope.node.vlan)) {
      $scope.vlan = VLANsManager.getItemFromList($scope.node.vlan.id);
    }

    // If node has less than 4 NUMA nodes, have them expanded them by default.
    if (node.numa_nodes && node.numa_nodes.length < 4) {
      $scope.expandedNumas = [...Array(node.numa_nodes.length).keys()];
    }
  }

  // Update the node with new data on the region.
  $scope.updateNode = function(node, queryPower) {
    if (angular.isUndefined(queryPower)) {
      queryPower = false;
    }

    return $scope.nodesManager
      .updateItem(node)
      .then(function() {
        updateHeader();
        updateSummary();
        if (queryPower) {
          $scope.checkPowerState();
        }
        $scope.failedUpdateError = "";
      })
      .catch(function(error) {
        $log.error(error);
        updateHeader();
        updateSummary();
        $scope.node.power_parameters = {};
        $scope.failedUpdateError = error;
      });
  };

  // Called for autocomplete when the user is typing a tag name.
  $scope.tagsAutocomplete = function(query) {
    return TagsManager.autocomplete(query);
  };

  $scope.getPowerStateClass = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return "";
    }

    if ($scope.checkingPower) {
      return "checking";
    } else {
      return $scope.node.power_state;
    }
  };

  // Get the power state text to show.
  $scope.getPowerStateText = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return "";
    }

    if ($scope.checkingPower) {
      return "Checking power";
    } else if ($scope.node.power_state === "unknown") {
      return "";
    } else {
      return "Power " + $scope.node.power_state;
    }
  };

  // Returns true when the "check now" button for updating the power
  // state should be shown.
  $scope.canCheckPowerState = function() {
    // This will get called very early and node can be empty.
    // In that case just return false. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return false;
    }
    return $scope.node.power_state !== "unknown" && !$scope.checkingPower;
  };

  // Check the power state of the node.
  $scope.checkPowerState = function() {
    $scope.checkingPower = true;
    $scope.nodesManager.checkPowerState($scope.node).then(function() {
      $scope.checkingPower = false;
    });
  };

  $scope.isUbuntuOS = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return false;
    }

    if ($scope.node.osystem === "ubuntu") {
      return true;
    }
    return false;
  };

  $scope.isUbuntuCoreOS = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return false;
    }

    if ($scope.node.osystem === "ubuntu-core") {
      return true;
    }
    return false;
  };

  $scope.isCentOS = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return false;
    }

    if ($scope.node.osystem === "centos" || $scope.node.osystem === "rhel") {
      return true;
    }
    return false;
  };

  $scope.isCustomOS = function() {
    // This will get called very early and node can be empty.
    // In that case just return an empty string. It will be
    // called again to show the correct information.
    if (!angular.isObject($scope.node)) {
      return false;
    }

    if ($scope.node.osystem === "custom") {
      return true;
    }
    return false;
  };

  // Return true if there is an action error.
  $scope.isActionError = function() {
    return $scope.action.error !== null;
  };

  // Return True if in deploy action and the osinfo is missing.
  $scope.isDeployError = function() {
    // Never a deploy error when there is an action error.
    if ($scope.isActionError()) {
      return false;
    }

    var missing_osinfo =
      angular.isUndefined($scope.osinfo.osystems) ||
      $scope.osinfo.osystems.length === 0;
    if (
      angular.isObject($scope.action.option) &&
      $scope.action.option.name === "deploy" &&
      missing_osinfo
    ) {
      return true;
    }
    return false;
  };

  // Return True if deploy warning should be shown because of missing ssh keys.
  $scope.isSSHKeyWarning = function() {
    // Never a deploy error when there is an action error.
    if ($scope.isActionError()) {
      return false;
    }
    if (
      angular.isObject($scope.action.option) &&
      $scope.action.option.name === "deploy" &&
      UsersManager.getSSHKeyCount() === 0
    ) {
      return true;
    }
    return false;
  };

  $scope.setDefaultValues = parameters => {
    const keys = Object.keys(parameters);

    keys.forEach(key => {
      if (parameters[key].default) {
        parameters[key].value = parameters[key].default;
      }
    });

    return parameters;
  };

  // Called when the actionOption has changed.
  $scope.action.optionChanged = function() {
    // Clear the action error.
    $scope.action.error = null;
    $scope.action.showing_confirmation = false;
    $scope.action.confirmation_message = "";
    $scope.action.confirmation_details = [];
  };

  // Cancel the action.
  $scope.actionCancel = function() {
    $scope.action.option = null;
    $scope.action.error = null;
    $scope.action.showing_confirmation = false;
    $scope.action.confirmation_message = "";
    $scope.action.confirmation_details = [];
    $scope.testSelection.forEach(script => {
      script.parameters = $scope.setDefaultValues(script.parameters);
    });
  };

  // Perform the action.
  $scope.actionGo = function() {
    let extra = {};
    let scriptInput = {};
    // Set deploy parameters if a deploy.
    if (
      $scope.action.option.name === "deploy" &&
      angular.isString($scope.osSelection.osystem) &&
      angular.isString($scope.osSelection.release)
    ) {
      // Set extra. UI side the release is structured os/release, but
      // when it is sent over the websocket only the "release" is
      // sent.
      extra.osystem = $scope.osSelection.osystem;
      var release = $scope.osSelection.release;
      release = release.split("/");
      release = release[release.length - 1];
      extra.distro_series = release;
      // hwe_kernel is optional so only include it if its specified
      if (
        angular.isString($scope.osSelection.hwe_kernel) &&
        ($scope.osSelection.hwe_kernel.indexOf("hwe-") >= 0 ||
          $scope.osSelection.hwe_kernel.indexOf("ga-") >= 0)
      ) {
        extra.hwe_kernel = $scope.osSelection.hwe_kernel;
      }
      let installKVM = $scope.deployOptions.installKVM;
      // KVM pod deployment required bionic.
      if (installKVM) {
        extra.osystem = "ubuntu";
        extra.distro_series = "bionic";
      }
      extra.install_kvm = installKVM;
    } else if ($scope.action.option.name === "commission") {
      extra.enable_ssh = $scope.commissionOptions.enableSSH;
      extra.skip_bmc_config = $scope.commissionOptions.skipBMCConfig;
      extra.skip_networking = $scope.commissionOptions.skipNetworking;
      extra.skip_storage = $scope.commissionOptions.skipStorage;
      extra.commissioning_scripts = [];
      for (let i = 0; i < $scope.commissioningSelection.length; i++) {
        extra.commissioning_scripts.push($scope.commissioningSelection[i].id);
      }
      if ($scope.commissionOptions.updateFirmware) {
        extra.commissioning_scripts.push("update_firmware");
      }
      if ($scope.commissionOptions.configureHBA) {
        extra.commissioning_scripts.push("configure_hba");
      }
      if (extra.commissioning_scripts.length === 0) {
        // Tell the region not to run any custom commissioning
        // scripts.
        extra.commissioning_scripts.push("none");
      }
      extra.testing_scripts = [];
      for (let i = 0; i < $scope.testSelection.length; i++) {
        extra.testing_scripts.push($scope.testSelection[i].id);
      }
      if (extra.testing_scripts.length === 0) {
        // Tell the region not to run any tests.
        extra.testing_scripts.push("none");
      }
    } else if ($scope.action.option.name === "test") {
      if (
        $scope.node.status_code === 6 &&
        !$scope.action.showing_confirmation
      ) {
        $scope.action.showing_confirmation = true;
        $scope.action.confirmation_message =
          $scope.type_name_title + " is in a deployed state.";
        return;
      }
      // Set the test options.
      extra.enable_ssh = $scope.commissionOptions.enableSSH;
      extra.testing_scripts = [];
      for (let i = 0; i < $scope.testSelection.length; i++) {
        extra.testing_scripts.push($scope.testSelection[i].id);
      }
      if (extra.testing_scripts.length === 0) {
        // Tell the region not to run any tests.
        extra.testing_scripts.push("none");
      }

      const testingScriptsWithUrlParam = $scope.testSelection.filter(test => {
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
    } else if ($scope.action.option.name === "release") {
      // Set the release options.
      extra.erase = $scope.releaseOptions.erase;
      extra.secure_erase = $scope.releaseOptions.secureErase;
      extra.quick_erase = $scope.releaseOptions.quickErase;
    } else if (
      $scope.action.option.name === "delete" &&
      $scope.type_name === "controller" &&
      !$scope.action.showing_confirmation
    ) {
      for (let i = 0; i < $scope.vlans.length; i++) {
        var vlan = $scope.vlans[i];
        if (vlan.primary_rack === $scope.node.system_id) {
          $scope.action.confirmation_details.push(
            $scope.node.fqdn +
              " is the primary rack controller for " +
              vlan.name
          );
        }
        if (vlan.secondary_rack === $scope.node.system_id) {
          $scope.action.confirmation_details.push(
            $scope.node.fqdn +
              " is the secondary rack controller for " +
              vlan.name
          );
        }
      }
      if ($scope.action.confirmation_details.length > 0) {
        $scope.action.confirmation_message +=
          $scope.type_name_title + " will be deleted.";
        $scope.action.showing_confirmation = true;
        return;
      }
    }

    $scope.nodesManager
      .performAction($scope.node, $scope.action.option.name, extra)
      .then(
        function() {
          // If the action was delete, then go back to listing.
          if ($scope.action.option.name === "delete") {
            $location.path("/machines");
          }
          $scope.action.option = null;
          $scope.action.error = null;
          $scope.action.showing_confirmation = false;
          $scope.action.confirmation_message = "";
          $scope.osSelection.$reset();
          $scope.commissionOptions.enableSSH = false;
          $scope.commissionOptions.skipBMCConfig = false;
          $scope.commissionOptions.skipNetworking = false;
          $scope.commissionOptions.skipStorage = false;
          $scope.commissionOptions.updateFirmware = false;
          $scope.commissionOptions.configureHBA = false;
          $scope.commissioningSelection = [];
          $scope.testSelection = [];
        },
        function(error) {
          $scope.action.error = error;
          $scope.testSelection.forEach(script => {
            script.parameters = $scope.setDefaultValues(script.parameters);
          });
        }
      );
  };

  // Return true if the authenticated user is super user.
  $scope.isSuperUser = function() {
    return UsersManager.isSuperUser();
  };

  // Return true if the authenticated user has `perm` on node.
  $scope.hasPermission = function(perm) {
    if (
      angular.isObject($scope.node) &&
      angular.isArray($scope.node.permissions)
    ) {
      return $scope.node.permissions.indexOf(perm) >= 0;
    }
    return false;
  };

  // Return true if their are usable architectures.
  $scope.hasUsableArchitectures = function() {
    return $scope.summary.architecture.options.length > 0;
  };

  // Return the placeholder text for the architecture dropdown.
  $scope.getArchitecturePlaceholder = function() {
    if ($scope.hasUsableArchitectures()) {
      return "Choose an architecture";
    } else {
      return "-- No usable architectures --";
    }
  };

  // Return true if the saved architecture is invalid.
  $scope.hasInvalidArchitecture = function() {
    if (angular.isObject($scope.node)) {
      return (
        !$scope.isDevice &&
        ($scope.node.architecture === "" ||
          $scope.summary.architecture.options.indexOf(
            $scope.node.architecture
          ) === -1)
      );
    } else {
      return false;
    }
  };

  // Return true if the current architecture selection is invalid.
  $scope.invalidArchitecture = function() {
    return (
      !$scope.isDevice &&
      !$scope.isController &&
      ($scope.summary.architecture.selected === "" ||
        $scope.summary.architecture.options.indexOf(
          $scope.summary.architecture.selected
        ) === -1)
    );
  };

  // Return true if at least a rack controller is connected to the
  // region controller.
  $scope.isRackControllerConnected = function() {
    // If power_types exist then a rack controller is connected.
    return $scope.power_types.length > 0;
  };

  // Return true if the node is locked
  $scope.isLocked = function() {
    if ($scope.node === null) {
      return false;
    }

    return $scope.node.locked;
  };

  // Return true when the edit buttons can be clicked.
  $scope.canEdit = function() {
    // Devices can be edited, if the user has the permission.
    if ($scope.isDevice) {
      return $scope.hasPermission("edit");
    }
    // Other nodes require the rack to be connected and the
    // machine to not be locked.
    return (
      $scope.isRackControllerConnected() &&
      $scope.hasPermission("edit") &&
      !$scope.isLocked()
    );
  };

  // Called to edit the domain name.
  $scope.editHeaderDomain = function() {
    if ($scope.canEdit()) {
      return;
    }

    // Do nothing if already editing because we don't want to reset
    // the current value.
    if ($scope.header.editing_domain) {
      return;
    }
    $scope.header.editing = false;
    $scope.header.editing_domain = true;

    // Set the value to the hostname, as hostname and domain are edited
    // using different fields.
    $scope.header.hostname.value = $scope.node.hostname;
  };

  // Called to edit the node name.
  $scope.editHeader = function() {
    if (!$scope.canEdit()) {
      return;
    }

    // Do nothing if already editing because we don't want to reset
    // the current value.
    if ($scope.header.editing) {
      return;
    }
    $scope.header.editing = true;
    $scope.header.editing_domain = false;

    // Set the value to the hostname, as hostname and domain are edited
    // using different fields.
    $scope.header.hostname.value = $scope.node.hostname;
  };

  // Return true when the hostname or domain in the header is invalid.
  $scope.editHeaderInvalid = function() {
    // Not invalid unless editing.
    if (!$scope.header.editing && !$scope.header.editing_domain) {
      return false;
    }

    // The value cannot be blank.
    var value = $scope.header.hostname.value;
    if (value.length === 0) {
      return true;
    }
    return !ValidationService.validateHostname(value);
  };

  // Called to cancel editing of the node hostname and domain.
  $scope.cancelEditHeader = function() {
    $scope.header.editing = false;
    $scope.header.editing_domain = false;
    updateHeader();
  };

  // Called to save editing of node hostname or domain.
  $scope.saveEditHeader = function() {
    // Does nothing if invalid.
    if ($scope.editHeaderInvalid()) {
      return;
    }
    $scope.header.editing = false;
    $scope.header.editing_domain = false;

    // Copy the node and make the changes.
    var node = angular.copy($scope.node);
    node.hostname = $scope.header.hostname.value;
    node.domain = $scope.header.domain.selected;

    // Update the node.
    $scope.updateNode(node);
  };

  // Called to enter edit mode in the summary section.
  $scope.editSummary = function() {
    if (!$scope.canEdit()) {
      return;
    }
    $scope.summary.editing = true;
  };

  // Called to cancel editing in the summary section.
  $scope.cancelEditSummary = function() {
    // Leave edit mode only if node has valid architecture.
    if ($scope.isDevice || $scope.isController) {
      $scope.summary.editing = false;
    } else if (!$scope.hasInvalidArchitecture()) {
      $scope.summary.editing = false;
    }
  };

  // Called to save the changes made in the summary section.
  $scope.saveEditSummary = function() {
    // Do nothing if invalidArchitecture.
    if ($scope.invalidArchitecture()) {
      return;
    }

    $scope.summary.editing = false;

    // Copy the node and make the changes.
    var node = angular.copy($scope.node);
    node.zone = angular.copy($scope.summary.zone.selected);
    node.pool = angular.copy($scope.summary.pool.selected);
    node.description = angular.copy($scope.summary.description);
    node.architecture = $scope.summary.architecture.selected;
    if ($scope.summary.min_hwe_kernel.selected === null) {
      node.min_hwe_kernel = "";
    } else {
      node.min_hwe_kernel = $scope.summary.min_hwe_kernel.selected;
    }
    node.tags = [];
    angular.forEach($scope.summary.tags, function(tag) {
      node.tags.push(tag.text);
    });

    // Update the node.
    $scope.updateNode(node);
  };

  // Return true if the current power type selection is invalid.
  $scope.invalidPowerType = function() {
    return !angular.isObject($scope.power.type);
  };

  // Called to enter edit mode in the power section.
  $scope.editPower = function() {
    if (!$scope.canEdit()) {
      return;
    }
    $scope.power.editing = true;
  };

  // Called to cancel editing in the power section.
  $scope.cancelEditPower = function() {
    // If the node is not a machine, only leave edit mode if node has
    // valid power type.
    if ($scope.node.node_type !== 0 || $scope.node.power_type !== "") {
      $scope.power.editing = false;
    }
    updatePower();
  };

  // Called to save the changes made in the power section.
  $scope.saveEditPower = function() {
    // Does nothing if invalid power type.
    if ($scope.invalidPowerType()) {
      return;
    }
    $scope.power.editing = false;

    // Copy the node and make the changes.
    var node = angular.copy($scope.node);
    node.power_type = $scope.power.type.name;
    node.power_parameters = angular.copy($scope.power.parameters);

    // Update the node.
    $scope.updateNode(node, true);
  };

  // Return true if the "load more" events button should be available.
  $scope.allowShowMoreEvents = function() {
    if (!angular.isObject($scope.node)) {
      return false;
    }
    if (!angular.isArray($scope.node.events)) {
      return false;
    }
    return (
      $scope.node.events.length > 0 &&
      $scope.node.events.length > $scope.events.limit &&
      $scope.events.limit < 50
    );
  };

  // Show another 10 events.
  $scope.showMoreEvents = function() {
    $scope.events.limit += 10;
  };

  // Return the nice text for the given event.
  $scope.getEventText = function(event) {
    var text = event.type.description;
    if (angular.isString(event.description) && event.description.length > 0) {
      text += " - " + event.description;
    }
    return text;
  };

  $scope.getPowerEventError = function() {
    if (
      !angular.isObject($scope.node) ||
      !angular.isArray($scope.node.events)
    ) {
      return;
    }

    var i;
    for (i = 0; i < $scope.node.events.length; i++) {
      var event = $scope.node.events[i];
      if (
        event.type.level === "warning" &&
        event.type.description === "Failed to query node's BMC"
      ) {
        // Latest power event is an error
        return event;
      } else if (
        event.type.level === "info" &&
        event.type.description === "Queried node's BMC"
      ) {
        // Latest power event is not an error
        return;
      }
    }
    // No power event found, thus no error
    return;
  };

  $scope.hasPowerEventError = function() {
    var event = $scope.getPowerEventError();
    return angular.isObject(event);
  };

  $scope.getPowerEventErrorText = function() {
    var event = $scope.getPowerEventError();
    if (angular.isObject(event)) {
      // Return text
      return event.description;
    } else {
      return "";
    }
  };

  // true if power error prevents the provided action
  $scope.hasActionPowerError = function(actionName) {
    if (!$scope.hasPowerError()) {
      return false; // no error, no need to check state
    }
    // these states attempt to manipulate power
    var powerChangingStates = ["commission", "deploy", "on", "off", "release"];
    if (actionName && powerChangingStates.indexOf(actionName) > -1) {
      return true;
    }
    return false;
  };

  // Check to see if the power type has any missing system packages.
  $scope.hasPowerError = function() {
    if (angular.isObject($scope.power.type)) {
      return $scope.power.type.missing_packages.length > 0;
    } else {
      return false;
    }
  };

  // Returns a formatted string of missing system packages.
  $scope.getPowerErrors = function() {
    var i;
    var result = "";
    if (angular.isObject($scope.power.type)) {
      var packages = $scope.power.type.missing_packages;
      packages.sort();
      for (i = 0; i < packages.length; i++) {
        result += packages[i];
        if (i + 2 < packages.length) {
          result += ", ";
        } else if (i + 1 < packages.length) {
          result += " and ";
        }
      }
      result += packages.length > 1 ? " packages" : " package";
    }
    return result;
  };

  // Return the class to apply to the service.
  $scope.getServiceClass = function(service) {
    if (!angular.isObject(service)) {
      return "none";
    } else {
      if (service.status === "running") {
        return "success";
      } else if (service.status === "dead") {
        return "error";
      } else if (service.status === "degraded") {
        return "warning";
      } else {
        return "none";
      }
    }
  };

  $scope.hasCustomCommissioningScripts = function() {
    var i;
    for (i = 0; i < $scope.scripts.length; i++) {
      if ($scope.scripts[i].script_type === 0) {
        return true;
      }
    }
    return false;
  };

  // Called by the children controllers to let the parent know.
  $scope.controllerLoaded = function(name, scope) {
    $scope[name] = scope;
    if (angular.isObject(scope.node)) {
      scope.nodeLoaded();
    }
  };

  // Only show a warning that tests have failed if there are failed tests
  // and the node isn't currently commissioning or testing.
  $scope.showFailedTestWarning = function() {
    // Devices can't have failed tests and don't have status_code
    // defined.
    if ($scope.node.node_type === 1 || !$scope.node.status_code) {
      return false;
    }
    switch ($scope.node.status_code) {
      // NEW
      case 0:
      // COMMISSIONING
      case 1: // eslint-disable-line no-fallthrough
      // FAILED_COMMISSIONING
      case 2: // eslint-disable-line no-fallthrough
      // TESTING
      case 21: // eslint-disable-line no-fallthrough
      // FAILED_TESTING
      case 22: // eslint-disable-line no-fallthrough
        return false;
    }
    switch ($scope.node.testing_status.status) {
      // Tests haven't been run
      case -1:
      // Tests have passed
      case 2: // eslint-disable-line no-fallthrough
        return false;
    }
    return true;
  };

  // Get the subtext for the CPU card. Only nodes commissioned after
  // MAAS 2.4 will have the CPU speed.
  $scope.getCPUSubtext = () => {
    const { node } = $scope;
    let text = "Unknown";

    if (node.cpu_count) {
      text = `${node.cpu_count} core${node.cpu_count > 1 ? "s" : ""}`;
    }
    if (node.cpu_speed) {
      const speedText =
        node.cpu_speed > 1000
          ? `${node.cpu_speed / 1000} GHz`
          : `${node.cpu_speed} MHz`;
      text += `, ${speedText}`;
    }
    return text;
  };

  $scope.getDHCPStatus = iface => {
    const { vlans } = $scope;
    const vlan = vlans.find(vlan => vlan.id === iface.vlan_id);
    if (vlan) {
      if (vlan.external_dhcp) {
        return `External (${vlan.external_dhcp})`;
      }

      if (vlan.dhcp_on) {
        return "MAAS-provided";
      }
    }
    return "No DHCP";
  };

  $scope.getFabricName = iface => {
    const { fabrics, vlans } = $scope;
    const vlan = vlans.find(vlan => vlan.id === iface.vlan_id);
    if (vlan) {
      const fabric = fabrics.find(fabric => fabric.id === vlan.fabric);
      if (fabric) {
        return fabric.name;
      }
    }
    return "Unknown";
  };

  $scope.hasTestsRun = (node, scriptType) => {
    const testObj = node[`${scriptType}_test_status`];
    return (
      testObj.passed + testObj.pending + testObj.running + testObj.failed > 0
    );
  };

  $scope.getHardwareTestErrorText = function(error) {
    if (error === "Unable to run destructive test while deployed!") {
      return (
        "The selected hardware tests contain one or more destructive" +
        " tests. Destructive tests cannot run on deployed machines."
      );
    } else {
      return error;
    }
  };

  $scope.powerParametersValid = function(power_parameters) {
    if (!angular.isObject(power_parameters)) {
      return false;
    }

    // If no keys in obj
    if (Object.keys(power_parameters).length === 0) {
      return false;
    }

    // Keys which are optional
    const optionalKeys = ["mac_address"];

    // If keys but no values in obj
    var hasParameters = false;

    Object.keys(power_parameters).forEach(function(key) {
      if (optionalKeys.includes(key)) {
        return true;
      }

      if (power_parameters[key] !== "") {
        hasParameters = true;
      } else {
        hasParameters = false;
      }
    });

    if (!hasParameters) {
      return false;
    }

    return true;
  };

  $scope.toggleNumaExpanded = numaIndex => {
    if ($scope.expandedNumas.includes(numaIndex)) {
      $scope.expandedNumas = $scope.expandedNumas.filter(i => i !== numaIndex);
    } else {
      $scope.expandedNumas = [...$scope.expandedNumas, numaIndex];
    }
  };

  // Reload osinfo when the page reloads
  $scope.$on("$routeUpdate", function() {
    GeneralManager.loadItems(["osinfo", "architectures", "min_hwe_kernels"]);
  });

  // Event has to be broadcast from here so cta directive can listen for it
  $scope.validateNetworkConfiguration = () => {
    const testAction = $scope.action.availableOptions.find(action => {
      return action.name === "test";
    });
    $scope.$broadcast("validate", testAction);
  };

  var page_managers;
  if ($location.path().indexOf("/controller") !== -1) {
    $scope.nodesManager = ControllersManager;
    page_managers = [ControllersManager, ScriptsManager, VLANsManager];
    $scope.isController = true;
    $scope.isDevice = false;
    $scope.type_name = "controller";
    $scope.type_name_title = "Controller";
    $rootScope.page = "controllers";
  } else if ($location.path().indexOf("/device") !== -1) {
    $scope.nodesManager = DevicesManager;
    page_managers = [DevicesManager];
    $scope.isController = false;
    $scope.isDevice = true;
    $scope.type_name = "device";
    $scope.type_name_title = "Device";
    $rootScope.page = "devices";
  } else {
    $scope.nodesManager = MachinesManager;
    page_managers = [MachinesManager, ScriptsManager];
    $scope.isController = false;
    $scope.isDevice = false;
    $scope.type_name = "machine";
    $scope.type_name_title = "Machine";
    $rootScope.page = "machines";
  }

  // Load all the required managers.
  ManagerHelperService.loadManagers(
    $scope,
    [
      ZonesManager,
      GeneralManager,
      UsersManager,
      TagsManager,
      DomainsManager,
      ServicesManager,
      ResourcePoolsManager,
      FabricsManager,
      VLANsManager
    ].concat(page_managers)
  ).then(function() {
    // Possibly redirected from another controller that already had
    // this node set to active. Only call setActiveItem if not already
    // the activeItem.
    var activeNode = $scope.nodesManager.getActiveItem();
    if (
      angular.isObject(activeNode) &&
      activeNode.system_id === $routeParams.system_id
    ) {
      nodeLoaded(activeNode);

      // Set flag for RSD navigation item.
      if (!$rootScope.showRSDLink) {
        GeneralManager.getNavigationOptions().then(
          res => ($rootScope.showRSDLink = res.rsd)
        );
      }
    } else {
      $scope.nodesManager.setActiveItem($routeParams.system_id).then(
        function(node) {
          nodeLoaded(node);
          if (angular.isObject($scope.node.vlan)) {
            if (
              localStorage.getItem(
                `hideHighAvailabilityNotification-${$scope.node.vlan.id}`
              )
            ) {
              $scope.hideHighAvailabilityNotification = true;
            }
          }
        },
        function(error) {
          ErrorService.raiseError(error);
        }
      );
      activeNode = $scope.nodesManager.getActiveItem();
    }
    if ($scope.isDevice) {
      $scope.ip_assignment = activeNode.ip_assignment;
    }
  });
}

export default NodeDetailsController;
