/* Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Pod Details Controller
 */

/* @ngInject */
function PodDetailsController(
  $scope,
  $rootScope,
  $location,
  $routeParams,
  $filter,
  PodsManager,
  GeneralManager,
  UsersManager,
  DomainsManager,
  ZonesManager,
  MachinesManager,
  ManagerHelperService,
  ErrorService,
  ResourcePoolsManager,
  SubnetsManager,
  VLANsManager,
  FabricsManager,
  SpacesManager,
  ValidationService,
  $log,
  $document
) {
  // Checks if on RSD page
  $scope.onRSDSection = PodsManager.onRSDSection;

  $rootScope.title = "Loading...";

  if ($scope.onRSDSection($routeParams.id)) {
    $rootScope.page = "rsd";
    $scope.pageType = "RSD";
  } else {
    $rootScope.page = "kvm";
    $scope.pageType = "KVM";
  }

  // Initial values.
  $scope.loaded = false;
  $scope.pod = null;
  $scope.podManager = PodsManager;
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
    inProgress: false,
    error: null
  };
  $scope.defaultInterface = {
    name: "default"
  };
  $scope.compose = {
    action: {
      name: "compose",
      title: "Compose",
      sentence: "compose"
    },
    obj: {
      storage: [
        {
          type: "local",
          size: 8,
          tags: [],
          pool: {},
          boot: true
        }
      ],
      requests: [],
      interfaces: [$scope.defaultInterface]
    }
  };
  $scope.power_types = GeneralManager.getData("power_types");
  $scope.domains = DomainsManager.getItems();
  $scope.zones = ZonesManager.getItems();
  $scope.pools = ResourcePoolsManager.getItems();
  $scope.section = {
    area: "summary"
  };
  $scope.machinesSearch = "pod-id:=invalid";
  $scope.editing = false;

  // Pod name section.
  $scope.name = {
    editing: false,
    value: ""
  };

  // Return true if at least a rack controller is connected to the
  // region controller.
  $scope.isRackControllerConnected = function() {
    // If power_types exist then a rack controller is connected.
    return $scope.power_types.length > 0;
  };

  // Return true when the edit buttons can be clicked.
  $scope.canEdit = function() {
    if (
      $scope.isRackControllerConnected() &&
      $scope.pod &&
      $scope.pod.permissions &&
      $scope.pod.permissions.indexOf("edit") !== -1
    ) {
      return true;
    } else {
      return false;
    }
  };

  // Called to edit the pod configuration.
  $scope.editPodConfiguration = function() {
    if (!$scope.canEdit()) {
      return;
    }
    $scope.editing = true;
  };

  // Called when the cancel or save button is pressed.
  $scope.exitEditPodConfiguration = function() {
    $scope.editing = false;
  };

  // Called to edit the pod name.
  $scope.editName = function() {
    if (!$scope.canEdit()) {
      return;
    }

    // Do nothing if already editing because we don't
    // want to reset the current value.
    if ($scope.name.editing) {
      return;
    }
    $scope.name.editing = true;
    $scope.name.value = $scope.pod.name;
  };

  // Return true when the pod name is invalid.
  $scope.editNameInvalid = function() {
    // Not invalid unless editing.
    if (!$scope.name.editing) {
      return false;
    }

    // The value cannot be blank.
    var value = $scope.name.value;
    if (value.length === 0) {
      return true;
    }
    return !ValidationService.validateHostname(value);
  };

  // Called to cancel editing of the pod name.
  $scope.cancelEditName = function() {
    $scope.name.editing = false;
    updateName();
  };

  // Called to save editing of pod name.
  $scope.saveEditName = function() {
    // Does nothing if invalid.
    if ($scope.editNameInvalid()) {
      return;
    }
    $scope.name.editing = false;

    // Copy the pod and make the changes.
    var pod = angular.copy($scope.pod);
    pod.name = $scope.name.value;

    // Update the pod.
    $scope.updatePod(pod);
  };

  function updateName() {
    // Don't update the value if in editing mode.
    // As this would overwrite the users changes.
    if ($scope.name.editing) {
      return;
    }
    $scope.name.value = $scope.pod.name;
  }

  // Update the pod with new data on the region.
  $scope.updatePod = function(pod) {
    return $scope.podManager.updateItem(pod).then(
      function() {
        updateName();
      },
      function(error) {
        $log.error(error);
        updateName();
      }
    );
  };

  // Return true if there is an action error.
  $scope.isActionError = function() {
    return $scope.action.error !== null;
  };

  // Called when the action.option has changed.
  $scope.actionOptionChanged = function() {
    // Clear the action error.
    $scope.action.error = null;
  };

  // Cancel the action.
  $scope.actionCancel = function() {
    $scope.action.option = null;
    $scope.action.error = null;
  };

  // Perform the action.
  $scope.actionGo = function() {
    $scope.action.inProgress = true;
    $scope.action.option.operation($scope.pod).then(
      function() {
        // If the action was delete, then go back to listing.
        if ($scope.action.option.name === "delete") {
          if ($scope.onRSDSection($routeParams.id)) {
            $location.path("/rsd");
          } else {
            $location.path("/kvm");
          }
        }
        $scope.action.inProgress = false;
        $scope.action.option = null;
        $scope.action.error = null;
      },
      function(error) {
        $scope.action.inProgress = false;
        $scope.action.error = error;
      }
    );
  };

  $scope.openSubnetOptions = function(iface) {
    angular.forEach($scope.compose.obj.interfaces, function(i) {
      i.showOptions = false;
    });
    iface.showOptions = true;
  };

  $scope.validateMachineCompose = function() {
    if ($scope.compose.obj.requests.length < 1) {
      $scope.updateRequests();
    }

    const requests = $scope.compose.obj.requests;
    const hostname = $scope.compose.obj.hostname;
    let valid = true;
    if (angular.isDefined(hostname) && hostname !== "") {
      valid = ValidationService.validateHostname(hostname);
    }

    requests.forEach(function(request) {
      if (request.size > request.available || request.size === "") {
        valid = false;
      }
    });

    return valid;
  };

  $scope.updateRequests = function() {
    var storages = $scope.compose.obj.storage;
    var requests = [];
    storages.forEach(function(storage) {
      var requestWithPool = requests.find(function(request) {
        return request.poolId === storage.pool.id;
      });
      if (requestWithPool) {
        requestWithPool.size += parseInt(storage.size, 10);
      } else {
        requests.push({
          poolId: storage.pool.id,
          size: storage.size,
          available: Math.round(storage.pool.available / 1000 / 1000 / 1000)
        });
      }
    });
    $scope.compose.obj.requests = requests;
  };

  // Prevents key input if input is not a number key code.
  $scope.numberOnly = function(evt) {
    var charCode = evt.which ? evt.which : event.keyCode;
    if (charCode > 31 && (charCode < 48 || charCode > 57)) {
      evt.preventDefault();
    }
  };

  $scope.openOptions = function(storage) {
    angular.forEach($scope.compose.obj.storage, function(disk) {
      disk.showOptions = false;
    });
    storage.showOptions = true;
    $scope.updateRequests();
  };

  $scope.closeOptions = function(storage) {
    storage.showOptions = false;
  };

  $scope.closeStorageOptions = function() {
    angular.forEach($scope.compose.obj.storage, function(disk) {
      disk.showOptions = false;
    });
  };

  // Return the title of the pod type.
  $scope.getPodTypeTitle = function() {
    var i;
    for (i = 0; i < $scope.power_types.length; i++) {
      var power_type = $scope.power_types[i];
      if (power_type.name === $scope.pod.type) {
        return power_type.description;
      }
    }
    return $scope.pod.type;
  };

  // Returns true if the pod is composable.
  $scope.canCompose = function() {
    if (
      angular.isObject($scope.pod) &&
      angular.isArray($scope.pod.permissions)
    ) {
      return (
        $scope.pod.permissions.indexOf("compose") >= 0 &&
        $scope.pod.capabilities.indexOf("composable") >= 0
      );
    } else {
      return false;
    }
  };

  // Opens the compose action menu.
  $scope.composeMachine = function() {
    $scope.action.option = $scope.compose.action;
    $scope.updateRequests();
  };

  // Calculate the available cores with overcommit applied
  $scope.availableWithOvercommit = PodsManager.availableWithOvercommit;

  // Strip trailing zero
  $scope.stripTrailingZero = function(value) {
    if (value) {
      return value.toString().replace(/[.,]0$/, "");
    }
  };

  // Called before the compose params is sent over the websocket.
  $scope.composePreProcess = function(params) {
    params = angular.copy(params);
    params.id = $scope.pod.id;
    // Sort boot disk first.
    var sorted = $scope.compose.obj.storage.sort(function(a, b) {
      if (a.boot === b.boot) {
        return 0;
      } else if (a.boot && !b.boot) {
        return -1;
      } else {
        return 1;
      }
    });
    // Create the storage constraint.
    var storage = [];
    angular.forEach(sorted, function(disk, idx) {
      var constraint = idx + ":" + disk.size;
      var tags = disk.tags.map(function(tag) {
        return tag.text;
      });
      if ($scope.pod.type === "rsd") {
        tags.splice(0, 0, disk.type);
      } else if ($scope.pod.type === "virsh") {
        tags.splice(0, 0, disk.pool.name);
      }
      constraint += "(" + tags.join(",") + ")";
      storage.push(constraint);
    });
    params.storage = storage.join(",");

    // Create the interface constraint.
    // <interface-name>:<key>=<value>[,<key>=<value>];...
    var interfaces = [];
    angular.forEach($scope.compose.obj.interfaces, function(iface) {
      let row = "";
      if (iface.ipaddress) {
        row = `${iface.name}:ip=${iface.ipaddress}`;
      } else if (iface.subnet) {
        row = `${iface.name}:subnet_cidr=${iface.subnet.cidr}`;
      }
      if (row) {
        interfaces.push(row);
      }
    });
    params.interfaces = interfaces.join(";");

    return params;
  };

  $scope.copyToClipboard = function($event) {
    var clipboardParent = $event.currentTarget.previousSibling;
    var clipboardValue = clipboardParent.previousSibling.value;
    var el = $document.createElement("textarea");
    el.value = clipboardValue;
    $document.body.appendChild(el);
    el.select();
    $document.execCommand("copy");
    $document.body.removeChild(el);
  };

  // Called to cancel composition.
  $scope.cancelCompose = function() {
    $scope.compose.obj = {
      storage: [
        {
          type: "local",
          size: 8,
          tags: [],
          pool: $scope.getDefaultStoragePool(),
          boot: true
        }
      ],
      requests: [],
      interfaces: [$scope.defaultInterface]
    };
    $scope.action.option = null;
  };

  $scope.hasMultipleRequests = function(storage) {
    if (storage.otherRequests > 0) {
      return true;
    }

    return false;
  };

  // Add another storage device.
  $scope.composeAddStorage = function() {
    var storage = {
      type: "local",
      size: 8,
      tags: [],
      pool: $scope.getDefaultStoragePool(),
      boot: false
    };

    // Close all open option menus in the storage table when creating
    // a new storage.
    $scope.closeStorageOptions();

    if ($scope.pod.capabilities.indexOf("iscsi_storage") >= 0) {
      storage.type = "iscsi";
    }

    $scope.compose.obj.storage.push(storage);
    $scope.updateRequests();
  };

  // Change which disk is the boot disk.
  $scope.composeSetBootDisk = function(storage) {
    angular.forEach($scope.compose.obj.storage, function(disk) {
      disk.boot = false;
    });
    storage.boot = true;
  };

  // Get the default pod pool
  $scope.getDefaultStoragePool = function() {
    var defaultPool = {};
    if ($scope.pod.storage_pools && $scope.pod.default_storage_pool) {
      defaultPool = $scope.pod.storage_pools.filter(
        pool => pool.id == $scope.pod.default_storage_pool
      )[0];
    }

    if (!$scope.selectedPoolId) {
      $scope.selectedPoolId = defaultPool.id;
    }

    return defaultPool;
  };

  // Remove a disk from storage config.
  $scope.composeRemoveDisk = function(storage) {
    var idx = $scope.compose.obj.storage.indexOf(storage);
    if (idx >= 0) {
      $scope.compose.obj.storage.splice(idx, 1);
    }
    $scope.updateRequests();
  };

  $scope.bySpace = function(spaceName) {
    return function(subnet) {
      if (spaceName && subnet.space !== null) {
        return subnet.space.name == spaceName;
      } else if (!spaceName) {
        return !subnet.space;
      }
    };
  };

  $scope.hasSpacelessSubnets = function() {
    return $scope.availableSubnets.some(subnet => !subnet.space);
  };

  $scope.selectSubnet = function(subnet, iface) {
    const idx = $scope.compose.obj.interfaces.indexOf(iface);
    const thisInterface = $scope.compose.obj.interfaces[idx];
    thisInterface.subnet = subnet;
    thisInterface.space = subnet.space;
    thisInterface.vlan = subnet.vlan;
    thisInterface.fabric = subnet.fabric;
    thisInterface.pxe = $scope.pod.boot_vlans.includes(subnet.vlan.id);
    $scope.closeOptions(iface);
    return subnet;
  };

  $scope.resetSubnetList = function(iface) {
    // Select first available subnet or clear list.
    let subnets = $scope.availableSubnets;

    if (iface.selectedSpace) {
      subnets = subnets.filter(subnet => {
        if (subnet.space) {
          return subnet.space.name === iface.selectedSpace;
        }
      });
    }

    if (subnets.length > 0) {
      iface.subnet = $scope.selectSubnet(subnets[0], iface);
    } else {
      iface.subnet = undefined;
    }
  };

  $scope.selectSubnetByIP = function(iface) {
    if (iface.ipaddress) {
      angular.forEach($scope.availableSubnets, function(subnet) {
        let inNetwork = ValidationService.validateIPInNetwork(
          iface.ipaddress,
          subnet.cidr
        );
        if (inNetwork) {
          iface.subnet = $scope.selectSubnet(subnet, iface);
        }
      });
    }
  };

  const _getSubnetDetails = function(originalSubnet) {
    const subnet = Object.assign({}, originalSubnet);

    if (subnet.name === subnet.cidr) {
      subnet.displayName = subnet.cidr;
    } else {
      subnet.displayName = `${subnet.cidr} (${subnet.name})`;
    }
    subnet.vlan = VLANsManager.getItemFromList(subnet.vlan);
    if (subnet.vlan) {
      subnet.fabric = FabricsManager.getItemFromList(subnet.vlan.fabric);
    }
    subnet.space = SpacesManager.getItemFromList(subnet.space);
    return subnet;
  };

  // Add interfaces.
  $scope.composeAddInterface = function() {
    // Remove default auto-assigned interface when
    // adding custom interfaces
    let defaultIdx = $scope.compose.obj.interfaces.indexOf(
      $scope.defaultInterface
    );
    if (defaultIdx >= 0) {
      $scope.compose.obj.interfaces.splice(defaultIdx, 1);
    }
    var iface = {
      name: `eth${$scope.compose.obj.interfaces.length}`
    };
    $scope.compose.obj.interfaces.push(iface);
  };

  // Remove an interface from interfaces config.
  $scope.composeRemoveInterface = function(iface) {
    var idx = $scope.compose.obj.interfaces.indexOf(iface);
    if (idx >= 0) {
      $scope.compose.obj.interfaces.splice(idx, 1);
    }

    // Re-add default interface if all custom interfaces removed
    if ($scope.compose.obj.interfaces.length == 0) {
      $scope.compose.obj.interfaces.push($scope.defaultInterface);
    }
  };

  // Start watching key fields.
  $scope.startWatching = function() {
    $scope.$watch("subnets", function() {
      angular.forEach($scope.subnets, function(subnet) {
        // filter subnets from vlans not attached to host
        if ($scope.pod.attached_vlans.includes(subnet.vlan)) {
          $scope.availableSubnets.push(_getSubnetDetails(subnet));
        }
      });
    });
    $scope.$watch("pod.name", function() {
      if ($scope.onRSDSection($scope.pod.id)) {
        $rootScope.title = "RSD " + $scope.pod.name;
      } else {
        $rootScope.title = "Pod " + $scope.pod.name;
      }
      updateName();
    });
    $scope.$watch("pod.capabilities", function() {
      // Show the composable action if the pod supports composition.
      var idx = $scope.action.options.indexOf($scope.compose.action);
      if (!$scope.canCompose()) {
        if (idx >= 0) {
          $scope.action.options.splice(idx, 1);
        }
      } else {
        if (idx === -1) {
          $scope.action.options.splice(0, 0, $scope.compose.action);
        }
      }
    });
    $scope.$watch("action.option", function(now, then) {
      // When the compose action is selected set the default
      // parameters.
      if (now && now.name === "compose") {
        if (!then || then.name !== "compose") {
          $scope.compose.obj.domain = DomainsManager.getDefaultDomain().id;
          $scope.compose.obj.zone = ZonesManager.getDefaultZone($scope.pod).id;
          $scope.compose.obj.pool = $scope.pod.default_pool;
        }
      }
    });
  };

  // Load all the required managers.
  ManagerHelperService.loadManagers($scope, [
    PodsManager,
    GeneralManager,
    UsersManager,
    DomainsManager,
    ZonesManager,
    MachinesManager,
    ResourcePoolsManager,
    SubnetsManager,
    VLANsManager,
    FabricsManager,
    SpacesManager
  ]).then(function() {
    $scope.spaces = SpacesManager.getItems();
    $scope.subnets = SubnetsManager.getItems();
    $scope.availableSubnets = [];

    // Possibly redirected from another controller that already had
    // this pod set to active. Only call setActiveItem if not already
    // the activeItem.
    var activePod = PodsManager.getActiveItem();
    if (
      angular.isObject(activePod) &&
      activePod.id === parseInt($routeParams.id, 10)
    ) {
      $scope.pod = activePod;
      $scope.compose.obj.storage[0].pool = $scope.getDefaultStoragePool();
      $scope.loaded = true;
      $scope.machinesSearch = "pod-id:=" + $scope.pod.id;
      $scope.startWatching();
    } else {
      PodsManager.setActiveItem(parseInt($routeParams.id, 10)).then(
        function(pod) {
          $scope.pod = pod;
          $scope.compose.obj.storage[0].pool = $scope.getDefaultStoragePool();
          $scope.loaded = true;
          $scope.machinesSearch = "pod-id:=" + $scope.pod.id;
          $scope.startWatching();

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

export default PodDetailsController;
