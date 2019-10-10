import { HardwareType } from "../enum";

/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Networking Controller
 */

// Filter that is specific to the NodeNetworkingController. Filters the
// list of VLANs to be only those that are unused by the interface.
export function filterByUnusedForInterface() {
  return function(vlans, nic, originalInterfaces) {
    var filtered = [];
    if (!angular.isObject(nic) || !angular.isObject(originalInterfaces)) {
      return filtered;
    }
    var usedVLANs = [];
    angular.forEach(originalInterfaces, function(inter) {
      if (inter.type === "vlan") {
        var parent = inter.parents[0];
        if (parent === nic.id) {
          usedVLANs.push(inter.vlan_id);
        }
      }
    });
    angular.forEach(vlans, function(vlan) {
      var idx = usedVLANs.indexOf(vlan.id);
      if (idx === -1) {
        filtered.push(vlan);
      }
    });
    return filtered;
  };
}

// Filter that is specific to the NodeNetworkingController. Filters the
// list of interfaces to not include the current parent interfaces being
// bonded together.
export function removeInterfaceParents() {
  return function(interfaces, childInterface, skip) {
    if (
      skip ||
      !angular.isObject(childInterface) ||
      !angular.isArray(childInterface.parents)
    ) {
      return interfaces;
    }
    var filtered = [];
    angular.forEach(interfaces, function(nic) {
      var i,
        parent,
        found = false;
      for (i = 0; i < childInterface.parents.length; i++) {
        parent = childInterface.parents[i];
        if (parent.id === nic.id && parent.link_id === nic.link_id) {
          found = true;
          break;
        }
      }
      if (!found) {
        filtered.push(nic);
      }
    });
    return filtered;
  };
}

// Filter that is specific to the NodeNetworkingController. Remove the default
// VLAN if the interface is a VLAN interface.
export function removeDefaultVLANIfVLAN() {
  return function(vlans, interfaceType) {
    if (!angular.isString(interfaceType)) {
      return vlans;
    }
    var filtered = [];
    angular.forEach(vlans, function(vlan) {
      if (interfaceType !== "vlan") {
        filtered.push(vlan);
      } else if (vlan.vid !== 0) {
        filtered.push(vlan);
      }
    });
    return filtered;
  };
}

// Filter that is specific to the NodeNetworkingController. Remove
// VLANs that are no part of current fabric.
export function filterVLANNotOnFabric() {
  return function(items, VLANsInFabric) {
    if (!angular.isArray(VLANsInFabric)) {
      return items;
    }

    return items.filter(function(item) {
      var index = VLANsInFabric.indexOf(item.id);
      return index !== -1;
    });
  };
}

function isOnSameFabric(item, bondInterface) {
  if (item.fabric && bondInterface.fabric) {
    return item.fabric.name === bondInterface.fabric.name;
  }

  return false;
}

function isOnSameVLAN(item, bondInterface) {
  if (item.vlan && bondInterface.vlan) {
    return item.vlan.id === bondInterface.vlan.id;
  }

  return false;
}

// Filter that is specific to the NodeNetworkingController. Remove
// editInterface from list.
export function filterEditInterface() {
  return function(items, editInterface) {
    if (!angular.isObject(editInterface)) {
      return items;
    }

    var results = items.filter(function(item) {
      return (
        item.id !== editInterface.id &&
        isOnSameFabric(item, editInterface) &&
        isOnSameVLAN(item, editInterface)
      );
    });

    return results;
  };
}

// Filter that is specific to the NodeNetworkingController. Remove the
// selected interfaces
export function filterSelectedInterfaces() {
  return function(items, selectedInterfaces, newBondInterface) {
    if (!angular.isArray(selectedInterfaces)) {
      return items;
    }

    if (!angular.isObject(newBondInterface)) {
      return items;
    }

    return items.filter(function(item) {
      var itemKey = item.id + "/" + item.link_id;

      return (
        selectedInterfaces.indexOf(itemKey) === -1 &&
        item.fabric.name === newBondInterface.fabric.name &&
        item.vlan.id === newBondInterface.vlan.id
      );
    });
  };
}

// Filter that is specific to the NodeNetworkingController. Only provide the
// available modes for that interface type.
export function filterLinkModes() {
  return function(modes, nic) {
    if (!angular.isObject(nic)) {
      return modes;
    }
    var filtered = [];

    // If this is not a $maasForm, make it work like one.
    // We need to use getValue() to access attributes, because each
    // type of maas-obj-form gets to define how values come out.
    if (!angular.isFunction(nic.getValue)) {
      nic.getValue = function(name) {
        return this[name];
      };
    }

    if (!angular.isObject(nic.getValue("subnet"))) {
      // No subnet is configure so the only allowed mode
      // is 'link_up'.
      angular.forEach(modes, function(mode) {
        if (mode.mode === "link_up") {
          filtered.push(mode);
        }
      });
    } else {
      // Don't add LINK_UP if more than one link exists or
      // if the interface is an alias.
      var links = nic.getValue("links");
      var nicType = nic.getValue("type");
      var allowLinkUp =
        (angular.isObject(links) && links.length > 1) || nicType === "alias";
      angular.forEach(modes, function(mode) {
        if (allowLinkUp && mode.mode === "link_up") {
          return;
        }
        // Can't run DHCP twice on one NIC.
        if (nicType === "alias" && mode.mode === "dhcp") {
          return;
        }
        filtered.push(mode);
      });
    }
    return filtered;
  };
}

/* @ngInject */
export function NodeNetworkingController(
  $scope,
  $rootScope,
  $filter,
  FabricsManager,
  VLANsManager,
  SubnetsManager,
  ControllersManager,
  GeneralManager,
  UsersManager,
  NodeResultsManagerFactory,
  ManagerHelperService,
  ValidationService,
  JSONService,
  DHCPSnippetsManager,
  $log,
  $routeParams
) {
  // Different interface types.
  var INTERFACE_TYPE = {
    PHYSICAL: "physical",
    BOND: "bond",
    BRIDGE: "bridge",
    VLAN: "vlan",
    ALIAS: "alias"
  };
  var INTERFACE_TYPE_TEXTS = {
    physical: "Physical",
    bond: "Bond",
    bridge: "Bridge",
    vlan: "VLAN",
    alias: "Alias",
    ovs: "Open vSwitch"
  };

  // Different link modes for an interface.
  var LINK_MODE = {
    AUTO: "auto",
    STATIC: "static",
    DHCP: "dhcp",
    LINK_UP: "link_up"
  };
  var LINK_MODE_TEXTS = {
    auto: "Auto assign",
    static: "Static assign",
    dhcp: "DHCP",
    link_up: "Unconfigured"
  };

  // Different selection modes.
  var SELECTION_MODE = {
    NONE: null,
    SINGLE: "single",
    MULTI: "multi",
    DELETE: "delete",
    ADD: "add",
    CREATE_BOND: "create-bond",
    CREATE_BRIDGE: "create-bridge",
    CREATE_PHYSICAL: "create-physical",
    EDIT: "edit"
  };

  var IP_ASSIGNMENT = {
    DYNAMIC: "dynamic",
    EXTERNAL: "external",
    STATIC: "static"
  };

  // Device ip assignment options.
  $scope.ipAssignments = [
    {
      name: IP_ASSIGNMENT.EXTERNAL,
      text: "External"
    },
    {
      name: IP_ASSIGNMENT.DYNAMIC,
      text: "Dynamic"
    },
    {
      name: IP_ASSIGNMENT.STATIC,
      text: "Static"
    }
  ];

  $scope.section = {
    area: angular.isString($routeParams.area) ? $routeParams.area : "summary"
  };

  // Set the initial values for this scope.
  $scope.loaded = false;
  $scope.nodeHasLoaded = false;
  $scope.managersHaveLoaded = false;
  $scope.tableInfo = { column: "name" };
  $scope.fabrics = FabricsManager.getItems();
  $scope.vlans = VLANsManager.getItems();
  $scope.subnets = SubnetsManager.getItems();
  $scope.interfaces = [];
  $scope.interfaceLinksMap = {};
  $scope.interfaceErrorsByLinkId = {};
  $scope.originalInterfaces = {};
  $scope.selectedInterfaces = [];
  $scope.selectedMode = null;
  $scope.newInterface = {};
  $scope.newBondInterface = {};
  $scope.newBridgeInterface = {};
  $scope.editInterface = null;
  $scope.bondOptions = GeneralManager.getData("bond_options");
  $scope.createBondError = null;
  $scope.newInterfaceLinkMonitoring = null;
  $scope.editInterfaceLinkMonitoring = null;
  $scope.isSaving = false;
  $scope.snippets = DHCPSnippetsManager.getItems();
  $scope.filteredSnippets = [];
  $scope.nodeResultsManager = null;
  $scope.networkTestingResults = null;
  $scope.modes = [
    {
      mode: LINK_MODE.AUTO,
      text: LINK_MODE_TEXTS[LINK_MODE.AUTO]
    },
    {
      mode: LINK_MODE.STATIC,
      text: LINK_MODE_TEXTS[LINK_MODE.STATIC]
    },
    {
      mode: LINK_MODE.DHCP,
      text: LINK_MODE_TEXTS[LINK_MODE.DHCP]
    },
    {
      mode: LINK_MODE.LINK_UP,
      text: LINK_MODE_TEXTS[LINK_MODE.LINK_UP]
    }
  ];

  $scope.isBond = item => item.type === "bond";
  $scope.isBridge = item => item.type === "bridge";
  $scope.isInterface = item => item.type === "physical";

  // Sets loaded to true if both the node has been loaded at the
  // other required managers for this scope have been loaded.
  function updateLoaded() {
    $scope.loaded = $scope.nodeHasLoaded && $scope.managersHaveLoaded;
    if ($scope.loaded) {
      updateInterfaces();
    }
  }

  // Update the list of interfaces for the node. For each link on the
  // interface, the interface is duplicated in the list to make render
  // in a data-ng-repeat easier.
  function updateInterfaces() {
    $scope.originalInterfaces = {};
    angular.forEach($scope.node.interfaces, function(nic) {
      $scope.originalInterfaces[nic.id] = nic;
    });

    var interfaces = [];
    // vlanTable contains data packaged for the 'Served VLANs' section,
    // which is essentially Interface LEFT JOIN VLAN LEFT JOIN Subnet.
    var vlanTable = [];
    // Keep track of VLAN IDs we've processed.
    var addedVlans = {};

    angular.forEach($scope.node.interfaces, function(nic) {
      // When a interface has a child that is a bond or bridge.
      // Then that interface is not included in the interface list.
      // Parent interface with a bond or bridge child can only have
      // one child.
      if (nic.children.length === 1) {
        var child = $scope.originalInterfaces[nic.children[0]];
        if (
          child.type === INTERFACE_TYPE.BOND ||
          child.type === INTERFACE_TYPE.BRIDGE
        ) {
          // This parent now has a bond or bridge for a child.
          // If this was the editInterface, then it needs to be
          // unset. We only need to check the "id" (not
          // the "link_id"), because if this interface did have
          // aliases they have now been removed.
          if (
            angular.isObject($scope.editInterface) &&
            $scope.editInterface.id === nic.id
          ) {
            $scope.editInterface = null;
            $scope.selectedMode = SELECTION_MODE.NONE;
          }
          return;
        }
      }

      // When the interface is a bond or a bridge, place the children
      // as members for that interface.
      if (
        nic.type === INTERFACE_TYPE.BOND ||
        nic.type === INTERFACE_TYPE.BRIDGE
      ) {
        nic.members = [];
        angular.forEach(nic.parents, function(parent) {
          nic.members.push(angular.copy($scope.originalInterfaces[parent]));
        });
      }

      // Format the tags when they have not already been formatted.
      if (
        angular.isArray(nic.tags) &&
        nic.tags.length > 0 &&
        !angular.isString(nic.tags[0].text)
      ) {
        nic.tags = formatTags(nic.tags);
      }

      nic.vlan = VLANsManager.getItemFromList(nic.vlan_id);
      if (angular.isObject(nic.vlan)) {
        nic.fabric = FabricsManager.getItemFromList(nic.vlan.fabric);

        // Build the vlanTable for controller detail page.
        if ($scope.$parent.isController) {
          // Skip duplicate VLANs (by id, they can share names).
          if (!Object.prototype.hasOwnProperty.call(addedVlans, nic.vlan.id)) {
            addedVlans[nic.vlan.id] = true;
            var vlanRecord = {
              fabric: nic.fabric,
              vlan: nic.vlan,
              subnets: $filter("filter")(
                $scope.subnets,
                { vlan: nic.vlan.id },
                true
              ),
              primary_rack: null,
              secondary_rack: null
            };

            if (angular.isObject(nic.fabric)) {
              vlanRecord.sort_key =
                nic.fabric.name + "|" + $scope.getVLANText(nic.vlan);
            }
            if (nic.vlan.primary_rack) {
              vlanRecord.primary_rack = ControllersManager.getItemFromList(
                nic.vlan.primary_rack
              );
            }
            if (nic.vlan.secondary_rack) {
              vlanRecord.secondary_rack = ControllersManager.getItemFromList(
                nic.vlan.secondary_rack
              );
            }
            vlanTable.push(vlanRecord);
          }
          // Sort the table by (VLANText, fabric.name).
          vlanTable.sort(function(a, b) {
            return a.sort_key.localeCompare(b.sort_key);
          });
        }
      }

      // Update the interface based on its links or duplicate the
      // interface if it has multiple links.
      if (nic.links.length === 0) {
        // No links on this interface. The interface is either
        // disabled or has no links (which means the interface
        // is in LINK_UP mode).
        nic.link_id = -1;
        nic.subnet = null;
        nic.mode = LINK_MODE.LINK_UP;
        nic.ip_address = "";
        interfaces.push(nic);
      } else {
        var idx = 0;
        angular.forEach(nic.links, function(link) {
          var nic_copy = angular.copy(nic);
          nic_copy.link_id = link.id;
          nic_copy.subnet = SubnetsManager.getItemFromList(link.subnet_id);
          nic_copy.mode = link.mode;
          nic_copy.ip_address = link.ip_address;
          if (angular.isUndefined(nic_copy.ip_address)) {
            nic_copy.ip_address = "";
          }
          // We don't want to deep copy the VLAN and fabric
          // object so we set those back to the original.
          nic_copy.vlan = nic.vlan;
          nic_copy.fabric = nic.fabric;
          if (idx > 0) {
            // Each extra link is an alais on the original
            // interface.
            nic_copy.type = INTERFACE_TYPE.ALIAS;
            nic_copy.name += ":" + idx;
          }
          idx++;
          interfaces.push(nic_copy);
        });
      }
    });

    // Update the scopes interfaces.
    $scope.interfaces = interfaces;
    $scope.vlanTable = vlanTable;

    $scope.snippets.forEach(snippet => {
      let subnet = SubnetsManager.getItemFromList(snippet.subnet);

      if (subnet) {
        snippet.subnet_cidr = subnet.cidr;
      }
    });

    let subnetIPs = [];

    $scope.interfaces.forEach(item => {
      if (item.subnet) {
        subnetIPs.push(item.subnet.cidr);
      }
    });

    $scope.filteredSnippets = $scope.snippets.filter(snippet => {
      return snippet.node === $scope.node.system_id;
    });

    // Update the scope interface links mapping.
    $scope.interfaceLinksMap = {};
    angular.forEach($scope.interfaces, function(nic) {
      var linkMaps = $scope.interfaceLinksMap[nic.id];
      if (angular.isUndefined(linkMaps)) {
        linkMaps = {};
        $scope.interfaceLinksMap[nic.id] = linkMaps;
      }
      linkMaps[nic.link_id] = nic;
    });

    // Clear the editInterface if it no longer exists in the
    // interfaceLinksMap.
    if (angular.isObject($scope.editInterface)) {
      var links = $scope.interfaceLinksMap[$scope.editInterface.id];
      if (angular.isUndefined(links)) {
        $scope.editInterface = null;
        $scope.selectedMode = SELECTION_MODE.NONE;
      } else {
        var link = links[$scope.editInterface.link_id];
        if (angular.isUndefined(link)) {
          $scope.editInterface = null;
          $scope.selectedMode = SELECTION_MODE.NONE;
        }
      }
    }

    // Update newInterface.parent if it has changed.
    updateNewInterface();
  }

  // Return the original link object for the given interface.
  function mapNICToOriginalLink(nic_id, link_id) {
    var originalInteface = $scope.originalInterfaces[nic_id];
    if (angular.isObject(originalInteface)) {
      var i,
        link = null;
      for (i = 0; i < originalInteface.links.length; i++) {
        link = originalInteface.links[i];
        if (link.id === link_id) {
          break;
        }
      }
      return link;
    } else {
      return null;
    }
  }

  // Leave single selection mode.
  function leaveSingleSelectionMode() {
    if (
      $scope.selectedMode === SELECTION_MODE.SINGLE ||
      $scope.selectedMode === SELECTION_MODE.ADD ||
      $scope.selectedMode === SELECTION_MODE.DELETE
    ) {
      $scope.selectedMode = SELECTION_MODE.NONE;
    }
  }

  // Update the new interface since the interfaces list has
  // been reloaded.
  function updateNewInterface() {
    if (angular.isObject($scope.newInterface.parent)) {
      var parentId = $scope.newInterface.parent.id;
      var linkId = $scope.newInterface.parent.link_id;
      var links = $scope.interfaceLinksMap[parentId];
      if (angular.isObject(links)) {
        var newParent = links[linkId];
        if (angular.isObject(newParent)) {
          $scope.newInterface.parent = newParent;

          var iType = $scope.newInterface.type;
          var isAlias = iType === INTERFACE_TYPE.ALIAS;
          var isVLAN = iType === INTERFACE_TYPE.VLAN;
          var canAddAlias = $scope.canAddAlias(newParent);
          var canAddVLAN = $scope.canAddVLAN(newParent);
          if (!canAddAlias && !canAddVLAN) {
            // Cannot do any adding now.
            $scope.newInterface = {};
            leaveSingleSelectionMode();
          } else {
            if (isAlias && !canAddAlias && canAddVLAN) {
              $scope.newInterface.type = "vlan";
              $scope.addTypeChanged();
            } else if (isVLAN && !canAddVLAN && canAddAlias) {
              $scope.newInterface.type = "alias";
              $scope.addTypeChanged();
            }
          }
          return;
        }
      }

      // Parent no longer exists. Exit the single selection modes.
      $scope.newInterface = {};
      leaveSingleSelectionMode();
    }
  }

  // Return the default VLAN for a fabric.
  function getDefaultVLAN(fabric) {
    return VLANsManager.getItemFromList(fabric.default_vlan_id);
  }

  // Return list of unused VLANs for an interface. Also remove the
  // ignoreVLANs from the returned list.
  function getUnusedVLANs(nic, ignoreVLANs) {
    var vlans = $filter("removeDefaultVLAN")($scope.vlans);
    vlans = $filter("filterByFabric")(vlans, nic.fabric);
    vlans = $filter("filterByUnusedForInterface")(
      vlans,
      nic,
      $scope.originalInterfaces
    );

    // Remove the VLAN's that should be ignored when getting the unused
    // VLANs. This is done to help the selection of the next default.
    if (angular.isUndefined(ignoreVLANs)) {
      ignoreVLANs = [];
    }
    angular.forEach(ignoreVLANs, function(vlan) {
      var i;
      for (i = 0; i < vlans.length; i++) {
        if (vlans[i].id === vlan.id) {
          vlans.splice(i, 1);
          break;
        }
      }
    });
    return vlans;
  }

  // Return the currently selected interface objects.
  function getSelectedInterfaces() {
    var interfaces = [];
    angular.forEach($scope.selectedInterfaces, function(key) {
      var splitKey = key.split("/");
      var links = $scope.interfaceLinksMap[splitKey[0]];
      if (angular.isObject(links)) {
        var nic = links[splitKey[1]];
        if (angular.isObject(nic)) {
          interfaces.push(nic);
        }
      }
    });
    return interfaces;
  }

  // Get the next available name.
  function getNextName(prefix) {
    var idx = 0;
    angular.forEach($scope.originalInterfaces, function(nic) {
      if (nic.name === prefix + idx) {
        idx++;
      }
    });
    return prefix + idx;
  }

  // Return the tags formatted for ngTagInput.
  function formatTags(tags) {
    var formatted = [];
    angular.forEach(tags, function(tag) {
      formatted.push({ text: tag });
    });
    return formatted;
  }

  // Called by $parent when the node has been loaded.
  $scope.nodeLoaded = function() {
    $scope.$watch("node.interfaces", updateInterfaces);
    // Watch subnets for the served VLANs section.
    if ($scope.$parent.isController) {
      $scope.$watch("subnets", updateInterfaces, true);
    }
    $scope.nodeResultsManager = NodeResultsManagerFactory.getManager(
      $scope.node,
      $scope.section.area
    );

    $scope.nodeResultsManager.loadItems().then(() => {
      const testingResults = $scope.nodeResultsManager.testing_results;
      $scope.networkTestingResults = testingResults.find(
        res => res.hardware_type === HardwareType.NETWORK
      ).results;
    });

    $scope.nodeHasLoaded = true;
    updateLoaded();
  };

  // Return true if only the name or mac address of an interface can
  // be edited.
  $scope.isLimitedEditingAllowed = function(nic) {
    if (!$scope.canEdit()) {
      // If the user is not the superuser, pretend it's not Ready.
      return false;
    }
    if ($scope.$parent.isController || $scope.$parent.isDevice) {
      // Controllers and Devices are never in limited mode.
      return false;
    }
    return (
      angular.isObject($scope.node) &&
      $scope.node.status === "Deployed" &&
      nic.type !== "vlan"
    );
  };

  // Return true if the networking information cannot be edited.
  // (it can't be changed when the node is in any state other
  // than Ready or Broken and the user is not a superuser)
  $scope.isAllNetworkingDisabled = function() {
    if (!$scope.canEdit() && !$scope.$parent.isDevice) {
      // If the user is not a superuser and not looking at a
      // device, disable the networking panel.
      return true;
    }
    if ($scope.$parent.isController || $scope.$parent.isDevice) {
      // Never disable the full networking panel when its a
      // Controller or Device.
      return false;
    }
    if (
      angular.isObject($scope.node) &&
      ["New", "Ready", "Failed testing", "Allocated", "Broken"].indexOf(
        $scope.node.status
      ) === -1
    ) {
      // If a non-controller node is not ready allocated, or broken,
      // disable networking panel.
      return true;
    }
    // User must be a superuser and the node must be
    // either ready or broken. Enable it.
    return false;
  };

  // Return true if the interface is the boot interface or has a parent
  // that is the boot interface.
  $scope.isBootInterface = function(nic) {
    if (!angular.isObject(nic)) {
      return false;
    }

    if (nic.is_boot && nic.type !== INTERFACE_TYPE.ALIAS) {
      return true;
    } else if (
      nic.type === INTERFACE_TYPE.BOND ||
      nic.type === INTERFACE_TYPE.BRIDGE
    ) {
      var i;
      for (i = 0; i < nic.members.length; i++) {
        if (nic.members[i].is_boot) {
          return true;
        }
      }
    }
    return false;
  };

  // Get the text for the type of the interface.
  $scope.getInterfaceTypeText = function(nic) {
    let text;
    let type = nic.type;

    if (nic.params && nic.params.bridge_type === "ovs") {
      type = nic.params.bridge_type;
    }

    text = INTERFACE_TYPE_TEXTS[type];

    if (angular.isDefined(text)) {
      return text;
    } else {
      return nic.type;
    }
  };

  // Get the text for the link mode of the interface.
  $scope.getLinkModeText = function(nic) {
    var text = LINK_MODE_TEXTS[nic.mode];
    if (angular.isDefined(text)) {
      return text;
    } else {
      return nic.mode;
    }
  };

  // Get the text to display in the VLAN dropdown.
  $scope.getVLANText = function(vlan) {
    if (!angular.isObject(vlan)) {
      return "";
    }

    if (vlan.vid === 0) {
      return "untagged";
    } else if (angular.isString(vlan.name) && vlan.name.length > 0) {
      return vlan.vid + " (" + vlan.name + ")";
    } else {
      return vlan.vid;
    }
  };

  // Get the text to display in the subnet dropdown.
  $scope.getSubnetText = function(subnet) {
    if (!angular.isObject(subnet)) {
      return "Unconfigured";
    } else if (
      angular.isString(subnet.name) &&
      subnet.name.length > 0 &&
      subnet.cidr !== subnet.name
    ) {
      return subnet.cidr + " (" + subnet.name + ")";
    } else {
      return subnet.cidr;
    }
  };

  // Get the subnet from its ID.
  $scope.getSubnet = function(subnetId) {
    return SubnetsManager.getItemFromList(subnetId);
  };

  // Show button for editing interfaces
  $scope.showEditButton = function(item, interfaces) {
    if (item.type !== "bond") {
      return false;
    }

    interfaces = $filter("filterEditInterface")(
      interfaces,
      $scope.editInterface
    );

    if (item.members.length <= 2 && !interfaces.length) {
      return false;
    }

    return true;
  };

  $scope.showCreateEditButton = function() {
    var items = $filter("filterSelectedInterfaces")(
      $scope.interfaces,
      $scope.selectedInterfaces,
      $scope.newBondInterface
    );

    if (items.length || $scope.selectedInterfaces.length > 2) {
      return true;
    }

    return false;
  };

  // Return True if the interface name that the user typed is invalid.
  $scope.isInterfaceNameInvalid = function(nic) {
    if (
      !angular.isObject(nic) ||
      !nic.hasOwnProperty("name") ||
      nic.name.length === 0
    ) {
      return true;
    } else if (angular.isArray($scope.node.interfaces)) {
      var i;
      for (i = 0; i < $scope.node.interfaces.length; i++) {
        var otherNic = $scope.node.interfaces[i];
        if (otherNic.name === nic.name && otherNic.id !== nic.id) {
          return true;
        }
      }
    }
    return false;
  };

  // Return True if the link mode select should be disabled.
  $scope.isLinkModeDisabled = function(nic) {
    // This is only disabled when a subnet has not been selected.
    if (angular.isFunction(nic.getValue)) {
      return !angular.isObject(nic.getValue("subnet"));
    } else {
      return !angular.isObject(nic.subnet);
    }
  };

  // Return the interface errors.
  $scope.getInterfaceError = function(nic) {
    if (angular.isDefined(nic.link_id) && nic.link_id >= 0) {
      return $scope.interfaceErrorsByLinkId[nic.link_id];
    }
    return null;
  };

  // Return True if the interface IP address that the user typed is
  // invalid.
  $scope.isIPAddressInvalid = function(nic) {
    if (angular.isString(nic.ip_address) && nic.mode === "static") {
      return (
        !ValidationService.validateIP(nic.ip_address) ||
        !ValidationService.validateIPInNetwork(nic.ip_address, nic.subnet.cidr)
      );
    } else {
      return false;
    }
  };

  // Return unique key for the interface.
  $scope.getUniqueKey = function(nic) {
    return nic.id + "/" + nic.link_id;
  };

  // Toggle selection of the interface.
  $scope.toggleInterfaceSelect = function(nic) {
    var key = $scope.getUniqueKey(nic);
    var idx = $scope.selectedInterfaces.indexOf(key);

    function removeSelectedInterface(index) {
      $scope.selectedInterfaces.splice(index, 1);
    }

    function interfaceIsSelected() {
      return idx > -1;
    }

    if (interfaceIsSelected()) {
      removeSelectedInterface(idx);
    } else {
      $scope.selectedInterfaces.push(key);
    }

    function removeCurrentItem(currentItem, items) {
      return items.filter(function(item) {
        var itemId = angular.isObject(item) ? item.id : item;
        return itemId !== currentItem.id;
      });
    }

    function getCurrentItem(currentItem, items) {
      return items.filter(function(item) {
        var itemId = angular.isObject(item) ? item.id : item;
        return itemId === currentItem.id;
      });
    }

    if ($scope.newBondInterface && $scope.newBondInterface.parents) {
      var parents = $scope.newBondInterface.parents;
      var filteredParents = removeCurrentItem(nic, parents);

      if (interfaceIsSelected()) {
        $scope.newBondInterface.parents = filteredParents;
        $scope.newBondInterface.primary = filteredParents[0];
        $scope.newBondInterface.mac_address = filteredParents[0].mac_address;
        if (!getCurrentItem(nic, $scope.interfaces)) {
          $scope.interfaces.push(nic);
        }
      } else {
        $scope.newBondInterface.parents.push(nic);
      }
    }

    function isMultipleSelectedInterfaces() {
      return $scope.selectedInterfaces.length > 1;
    }

    if (isMultipleSelectedInterfaces()) {
      if ($scope.selectedMode !== SELECTION_MODE.BOND) {
        if (!$scope.isShowingCreateBond()) {
          $scope.selectedMode = SELECTION_MODE.MULTI;
        }
      }
    } else if ($scope.selectedInterfaces.length === 1) {
      if (!$scope.isShowingCreateBond()) {
        $scope.selectedMode = SELECTION_MODE.SINGLE;
      }
    } else {
      if (!$scope.isShowingCreateBond()) {
        $scope.selectedMode = SELECTION_MODE.NONE;
      }
    }
  };

  $scope.toggleEditInterfaceSelect = function(nic) {
    var key = $scope.getUniqueKey(nic);
    var keyIndex = $scope.selectedInterfaces.indexOf(key);

    if (keyIndex === -1) {
      // Select item
      $scope.selectedInterfaces.push(key);

      // Add to members
      if (
        !$scope.editInterface.members.find(function(item) {
          return item.id === nic.id;
        })
      ) {
        $scope.editInterface.members.push(nic);
      }

      // Add to parents
      if (
        !$scope.editInterface.parents.find(function(item) {
          return item === nic.id;
        })
      ) {
        $scope.editInterface.parents.push(nic.id);
      }

      // Remove from unselected rows
      var selectedInterface = $scope.interfaces.find(function(item) {
        return item.id === nic.id;
      });

      var selectedIndex = $scope.interfaces.indexOf(selectedInterface);

      if (selectedIndex !== -1) {
        $scope.interfaces.splice(selectedIndex, 1);
      }
    } else {
      // Unselect item
      $scope.selectedInterfaces.splice(keyIndex, 1);

      // Add to unselected rows
      if (
        !$scope.interfaces.find(function(item) {
          return item.id === nic.id;
        })
      ) {
        nic.fabric = $scope.editInterface.fabric;
        nic.vlan = $scope.editInterface.vlan;
        $scope.interfaces.push(nic);
      }

      // Remove from members
      var member = $scope.editInterface.members.find(function(item) {
        return item.id === nic.id;
      });

      var memberIndex = $scope.editInterface.members.indexOf(member);

      if (memberIndex !== -1) {
        $scope.editInterface.members.splice(memberIndex, 1);
      }

      // Remove from parents
      var parentIndex = $scope.editInterface.parents.indexOf(nic.id);

      if (parentIndex !== -1) {
        $scope.editInterface.parents.splice(parentIndex, 1);
      }

      // Reset primary and mac address
      var primaryMember = $scope.editInterface.members[0];

      if ($scope.editInterface.primary.id === nic.id) {
        $scope.editInterface.primary = primaryMember;
      }

      if (
        $scope.editInterface.mac_address === nic.mac_address &&
        primaryMember
      ) {
        $scope.editInterface.mac_address = primaryMember.mac_address;
      }
    }
  };

  // Return true when the interface is selected.
  $scope.isInterfaceSelected = function(nic) {
    return $scope.selectedInterfaces.indexOf($scope.getUniqueKey(nic)) > -1;
  };

  // Returns true if the interface is not selected
  $scope.cannotEditInterface = function(nic) {
    if ($scope.selectedMode === SELECTION_MODE.NONE) {
      return false;
    } else if (
      $scope.selectedMode !== SELECTION_MODE.MULTI &&
      $scope.isInterfaceSelected(nic)
    ) {
      return false;
    } else {
      return true;
    }
  };

  // Return true if in editing mode for the interface.
  $scope.isEditing = function(nic) {
    if ($scope.selectedMode !== SELECTION_MODE.EDIT) {
      return false;
    } else {
      return $scope.editInterface.id === nic.id;
    }
  };

  // Start editing this interface.
  $scope.edit = function(nic) {
    $scope.isShowingInterfaces = false;
    $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
    $scope.selectedMode = SELECTION_MODE.EDIT;
    if ($scope.$parent.isDevice) {
      $scope.editInterface = {
        id: nic.id,
        name: nic.name,
        mac_address: nic.mac_address,
        tags: nic.tags.map(function(tag) {
          return tag.text;
        }),
        subnet: nic.subnet,
        ip_address: nic.ip_address,
        ip_assignment: nic.ip_assignment,
        link_id: nic.link_id,
        link_connected: nic.link_connected,
        link_speed: nic.link_speed,
        interface_speed: nic.interface_speed,
        type: nic.type,
        bridge_fd: nic.params.bridge_fd,
        bridge_stp: nic.params.bridge_stp,
        bridge_type: nic.params.bridge_type,
        bond_mode: nic.params.bond_mode,
        xmitHashPolicy: nic.params.bond_xmit_hash_policy,
        lacpRate: nic.params.bond_lacp_rate,
        bond_downdelay: nic.params.bond_downdelay,
        bond_updelay: nic.params.bond_updelay,
        bond_miimon: nic.params.bond_miimon
      };
      if (angular.isDefined(nic.subnet) && nic.subnet !== null) {
        $scope.editInterface.defaultSubnet = nic.subnet;
      } else {
        $scope.editInterface.defaultSubnet = $scope.subnets[0];
      }
    } else {
      $scope.editInterface = {
        id: nic.id,
        name: nic.name,
        mac_address: nic.mac_address,
        tags: nic.tags.map(function(tag) {
          return tag.text;
        }),
        fabric: nic.fabric,
        vlan: nic.vlan,
        subnet: nic.subnet,
        mode: nic.mode,
        ip_address: nic.ip_address,
        link_id: nic.link_id,
        link_connected: nic.link_connected,
        link_speed: nic.link_speed,
        interface_speed: nic.interface_speed,
        type: nic.type,
        bridge_fd: nic.params.bridge_fd,
        bridge_stp: nic.params.bridge_stp,
        bridge_type: nic.params.bridge_type,
        bond_mode: nic.params.bond_mode,
        xmitHashPolicy: nic.params.bond_xmit_hash_policy,
        lacpRate: nic.params.bond_lacp_rate,
        bond_downdelay: nic.params.bond_downdelay,
        bond_updelay: nic.params.bond_updelay,
        bond_miimon: nic.params.bond_miimon
      };

      $scope.editInterface.parents = nic.parents;
      $scope.editInterface.members = nic.members;
      if (nic.members && nic.members.length) {
        $scope.editInterface.primary = nic.members[0];
      } else {
        $scope.editInterface.primary = null;
      }

      if (nic.members) {
        nic.members.forEach(function(member) {
          $scope.selectedInterfaces.push($scope.getUniqueKey(member));
        });
      }
    }
  };

  // Called when the fabric is changed.
  $scope.fabricChanged = function(nic) {
    // Update the VLAN on the node to be the default VLAN for that
    // fabric. The first VLAN for the fabric is the default.
    if (nic.fabric !== null) {
      nic.vlan = getDefaultVLAN(nic.fabric);
    } else {
      nic.vlan = null;
    }
    $scope.vlanChanged(nic);
  };

  // Called when the fabric is changed in a maas-obj-form.
  $scope.fabricChangedForm = function(key, value, form) {
    var vlan;
    if (value !== null) {
      vlan = getDefaultVLAN(value);
    } else {
      vlan = null;
    }
    form.updateValue("vlan", vlan);
    $scope.vlanChangedForm("vlan", vlan, form);
  };

  // Called when the VLAN is changed.
  $scope.vlanChanged = function(nic) {
    nic.subnet = null;
    $scope.subnetChanged(nic);
  };

  // Called when the VLAN is changed on a maas-obj-form
  $scope.vlanChangedForm = function(key, value, form) {
    form.updateValue("subnet", null);
    $scope.subnetChangedForm("subnet", null, form);
  };

  // Called when the subnet is changed.
  $scope.subnetChanged = function(nic) {
    if (!angular.isObject(nic.subnet)) {
      // Set to 'Unconfigured' so the link mode should be set to
      // 'link_up'.
      nic.mode = LINK_MODE.LINK_UP;
    }
    if ($scope.$parent.isDevice) {
      nic.ip_address = null;
    }
    $scope.modeChanged(nic);
  };

  // Called when the subnet is changed.
  $scope.subnetChangedForm = function(key, value, form) {
    if (!angular.isObject(value)) {
      // Set to 'Unconfigured' so the link mode should be set to
      // 'link_up'.
      form.updateValue("mode", LINK_MODE.LINK_UP);
    }
    const mode = form.getValue("mode");
    form.updateValue("ip_address", null);
    $scope.modeChangedForm("mode", mode, form);
  };

  // Called when the mode is changed.
  $scope.modeChanged = function(nic) {
    // Clear the IP address when the mode is changed.
    nic.ip_address = "";
    if (nic.mode === "static") {
      var originalLink = mapNICToOriginalLink(nic.id, nic.link_id);
      if (
        angular.isObject(originalLink) &&
        nic.subnet.id === originalLink.subnet_id
      ) {
        // Set the original IP address if same subnet.
        nic.ip_address = originalLink.ip_address;
      } else {
        nic.ip_address = nic.subnet.statistics.first_address;
      }
    }
  };

  // Update VLAN when fabric changed
  $scope.updateVLAN = function(nic) {
    var vlans = $filter("filterVLANNotOnFabric")(
      $scope.vlans,
      nic.fabric.vlan_ids
    );
    nic.vlan = vlans[0];
  };

  // Called when the mode is changed on a maas-obj-form.
  $scope.modeChangedForm = function(key, value, form) {
    // Clear the IP address when the mode is changed.
    form.updateValue("ip_address", "");
    if (value === "static") {
      var originalLink = mapNICToOriginalLink(
        form.getValue("id"),
        form.getValue("link_id")
      );
      if (
        angular.isObject(originalLink) &&
        form.getValue("subnet").id === originalLink.subnet_id
      ) {
        // Set the original IP address if same subnet.
        form.updateValue("ip_address", originalLink.ip_address);
      }
    }
  };

  // Called to cancel edit mode.
  $scope.editCancel = function() {
    $scope.isShowingInterfaces = false;
    $scope.selectedInterfaces = [];
    $scope.selectedMode = SELECTION_MODE.NONE;
    $scope.editInterface = null;
    updateInterfaces();
  };

  // Preprocess things for updateInterfaceForm.
  $scope.preProcessInterface = function(nic) {
    var params = angular.copy(nic);
    $scope.isSaving = true;

    delete params.id;
    params.system_id = $scope.node.system_id;
    params.interface_id = nic.id;

    // we need IDs not objects.
    if (angular.isDefined(nic.fabric) && nic.fabric !== null) {
      params.fabric = nic.fabric.id;
    } else {
      params.fabric = null;
    }
    if (angular.isDefined(nic.vlan) && nic.vlan !== null) {
      params.vlan = nic.vlan.id;
    } else {
      params.vlan = null;
    }
    if (angular.isDefined(nic.subnet) && nic.subnet !== null) {
      params.subnet = params.subnet.id;
    } else {
      delete params.subnet;
    }
    if (angular.isUndefined(nic.bridge_stp) && nic.bridge_stp === null) {
      params.bridge_stp = null;
    }
    if (angular.isUndefined(nic.bridge_fd) && nic.bridge_fd === null) {
      params.bridge_fd = null;
    }
    if (angular.isUndefined(nic.bond_mode) && nic.bond_mode === null) {
      params.bond_mode = null;
    }

    if (angular.isDefined(nic.link_id) && nic.link_id >= 0) {
      params.link_id = nic.link_id;
      delete $scope.interfaceErrorsByLinkId[nic.link_id];
    } else {
      delete params.link_id;
    }
    if (
      (nic.mode === LINK_MODE.STATIC ||
        nic.ip_assignment !== IP_ASSIGNMENT.DYNAMIC) &&
      angular.isString(nic.ip_address) &&
      nic.ip_address.length > 0
    ) {
      params.ip_address = nic.ip_address;
    } else {
      delete params.ip_address;
    }
    if (nic.tags) {
      params.tags = nic.tags.map(tag => tag.text);
    }
    return params;
  };

  // Save the following interface on the node.
  $scope.saveInterface = function(nic) {
    var params;
    if ($scope.$parent.isDevice) {
      params = {
        name: nic.name,
        mac_address: nic.mac_address,
        ip_assignment: nic.ip_assignment,
        ip_address: nic.ip_address
      };
    } else {
      params = {
        name: nic.name,
        mac_address: nic.mac_address,
        mode: nic.mode,
        tags: nic.tags.map(function(tag) {
          return tag.text;
        })
      };
    }
    if (angular.isDefined(nic.fabric) && nic.fabric !== null) {
      params.fabric = nic.fabric.id;
    } else {
      params.fabric = null;
    }
    if (angular.isDefined(nic.vlan) && nic.vlan !== null) {
      params.vlan = nic.vlan.id;
    } else {
      params.vlan = null;
    }
    if (angular.isDefined(nic.subnet) && nic.subnet !== null) {
      params.subnet = nic.subnet.id;
    } else {
      params.subnet = null;
    }
    if (angular.isDefined(nic.link_id) && nic.link_id >= 0) {
      params.link_id = nic.link_id;
      delete $scope.interfaceErrorsByLinkId[nic.link_id];
    }
    if (angular.isString(nic.ip_address) && nic.ip_address.length > 0) {
      params.ip_address = nic.ip_address;
    }
    return $scope.$parent.nodesManager
      .updateInterface($scope.node, nic.id, params)
      .then(null, function(error) {
        // XXX blake_r: Just log the error in the console, but
        // we need to expose this as a better message to the
        // user.
        $log.error(error);

        // Update the interfaces so it is back to the way it
        // was before the user changed it.
        updateInterfaces();
      });
  };

  // Save the following link on the node.
  $scope.saveInterfaceLink = function(nic) {
    var params = {
      mode: nic.mode
    };
    if ($scope.$parent.isDevice) {
      params.ip_assignment = nic.ip_assignment;
    }
    if (angular.isObject(nic.subnet)) {
      params.subnet = nic.subnet.id;
    }
    if (angular.isDefined(nic.link_id) && nic.link_id >= 0) {
      params.link_id = nic.link_id;
      delete $scope.interfaceErrorsByLinkId[nic.link_id];
    }
    if (
      nic.mode === LINK_MODE.STATIC &&
      angular.isString(nic.ip_address) &&
      nic.ip_address.length > 0
    ) {
      params.ip_address = nic.ip_address;
    }
    return $scope.$parent.nodesManager
      .linkSubnet($scope.node, nic.id, params)
      .then(null, function(error) {
        $log.info(error);
        if (angular.isDefined(nic.link_id) && nic.link_id >= 0) {
          $scope.interfaceErrorsByLinkId[nic.link_id] = error;
        }
        // Update the interfaces so it is back to the way it
        // was before the user changed it.
        updateInterfaces();
        throw error;
      });
  };

  // Called to save the interface.
  $scope.editSave = function(editInterface) {
    $scope.isSaving = false;
    $scope.editCancel();
    return editInterface;
  };

  // Return true if the interface delete confirm is being shown.
  $scope.isShowingDeleteConfirm = function() {
    return $scope.selectedMode === SELECTION_MODE.DELETE;
  };

  // Return true if the interface add interface is being shown.
  $scope.isShowingAdd = function() {
    return $scope.selectedMode === SELECTION_MODE.ADD;
  };

  // Return true if either an alias or VLAN can be added.
  $scope.canAddAliasOrVLAN = function(nic) {
    if ($scope.$parent.isController) {
      return false;
    } else if ($scope.isAllNetworkingDisabled()) {
      return false;
    } else {
      return $scope.canAddAlias(nic) || $scope.canAddVLAN(nic);
    }
  };

  // Return true if the alias can be added to interface.
  $scope.canAddAlias = function(nic) {
    if (!angular.isObject(nic)) {
      return false;
    } else if (nic.type === INTERFACE_TYPE.ALIAS) {
      return false;
    } else if (
      nic.links.length === 0 ||
      nic.links[0].mode === LINK_MODE.LINK_UP
    ) {
      return false;
    } else {
      return true;
    }
  };

  // Return true if the VLAN can be added to interface.
  $scope.canAddVLAN = function(nic) {
    if (!angular.isObject(nic)) {
      return false;
    } else if (
      nic.type === INTERFACE_TYPE.ALIAS ||
      nic.type === INTERFACE_TYPE.VLAN
    ) {
      return false;
    }
    var unusedVLANs = getUnusedVLANs(nic);
    return unusedVLANs.length > 0;
  };

  // Return true if another VLAN can be added to this already being
  // added interface.
  $scope.canAddAnotherVLAN = function(nic) {
    if (!$scope.canAddVLAN(nic)) {
      return false;
    }
    var unusedVLANs = getUnusedVLANs(nic);
    return unusedVLANs.length > 1;
  };

  // Return the text to use for the remove link and message.
  $scope.getRemoveTypeText = function(nic) {
    if (nic.type === INTERFACE_TYPE.PHYSICAL) {
      return "interface";
    } else if (nic.type === INTERFACE_TYPE.VLAN) {
      return "VLAN";
    } else {
      return nic.type;
    }
  };

  // Return true if the interface can be removed.
  $scope.canBeRemoved = function() {
    return !$scope.$parent.isController && !$scope.isAllNetworkingDisabled();
  };

  // Enter remove mode.
  $scope.remove = function() {
    $scope.selectedMode = SELECTION_MODE.DELETE;
  };

  // Quickly enter remove by selecting the node first.
  $scope.quickRemove = function(nic) {
    $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
    $scope.remove();
  };

  // Cancel the current mode go back to sinle selection mode.
  $scope.cancel = function() {
    $scope.isShowingInterfaces = false;
    $scope.newInterface = {};
    $scope.newBondInterface = {};
    $scope.newBridgeInterface = {};
    $scope.isChangingConnectionStatus = false;
    $scope.showEditWarning = false;
    $scope.clearCreateBondError();
    if ($scope.selectedMode === SELECTION_MODE.CREATE_BOND) {
      $scope.selectedMode = SELECTION_MODE.MULTI;
    } else if ($scope.selectedMode === SELECTION_MODE.CREATE_PHYSICAL) {
      $scope.selectedMode = SELECTION_MODE.NONE;
    } else {
      $scope.selectedMode = SELECTION_MODE.SINGLE;
    }
  };

  // Confirm the removal of interface.
  $scope.confirmRemove = function(nic) {
    $scope.selectedMode = SELECTION_MODE.NONE;
    $scope.selectedInterfaces = [];
    if (nic.type !== INTERFACE_TYPE.ALIAS) {
      $scope.$parent.nodesManager.deleteInterface($scope.node, nic.id);
    } else {
      $scope.$parent.nodesManager.unlinkSubnet(
        $scope.node,
        nic.id,
        nic.link_id
      );
    }

    // Remove the interface from available interfaces
    var idx = $scope.interfaces.indexOf(nic);
    if (idx > -1) {
      $scope.interfaces.splice(idx, 1);
    }
  };

  // Enter add mode.
  $scope.add = function(type, nic) {
    // When this is called right after another VLAN was just added, we
    // remove its used VLAN from the available list.
    var ignoreVLANs = [];
    if (angular.isObject($scope.newInterface.vlan)) {
      ignoreVLANs.push($scope.newInterface.vlan);
    }

    // Get the default VLAN for the new interface.
    var vlans = getUnusedVLANs(nic, ignoreVLANs);
    var defaultVLAN = null;
    if (vlans.length > 0) {
      defaultVLAN = vlans[0];
    }
    var defaultSubnet = null;
    var defaultMode = LINK_MODE.LINK_UP;

    // Alias used defaults based from its parent.
    if (type === INTERFACE_TYPE.ALIAS) {
      defaultVLAN = nic.vlan;
      defaultSubnet = $filter("filter")(
        $scope.subnets,
        { vlan: defaultVLAN.id },
        true
      )[0];
      defaultMode = LINK_MODE.AUTO;
    }

    // Setup the new interface and enter add mode.
    $scope.newInterface = {
      type: type,
      vlan: defaultVLAN,
      subnet: defaultSubnet,
      mode: defaultMode,
      parent: nic,
      tags: []
    };
    $scope.selectedMode = SELECTION_MODE.ADD;
  };

  // Quickly enter add by selecting the node first.
  $scope.quickAdd = function(nic) {
    $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
    var type = "alias";
    if (!$scope.canAddAlias(nic)) {
      type = "vlan";
    }
    $scope.add(type, nic);
  };

  // Return the name of the interface being added.
  $scope.getAddName = function() {
    if ($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
      var aliasIdx = $scope.newInterface.parent.links.length;
      return $scope.newInterface.parent.name + ":" + aliasIdx;
    } else if ($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
      return (
        $scope.newInterface.parent.name + "." + $scope.newInterface.vlan.vid
      );
    }
  };

  // Called when the type of interface is changed.
  $scope.addTypeChanged = function() {
    if ($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
      $scope.newInterface.vlan = $scope.newInterface.parent.vlan;
      $scope.newInterface.subnet = $filter("filter")(
        $scope.subnets,
        { vlan: $scope.newInterface.vlan.id },
        true
      )[0];
      $scope.newInterface.mode = LINK_MODE.AUTO;
    } else if ($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
      var vlans = getUnusedVLANs($scope.newInterface.parent);
      $scope.newInterface.vlan = null;
      if (vlans.length > 0) {
        $scope.newInterface.vlan = vlans[0];
      }
      $scope.newInterface.subnet = null;
      $scope.newInterface.mode = LINK_MODE.LINK_UP;
    }
  };

  // Perform the add action over the websocket.
  $scope.addInterface = function(type) {
    var nic;
    if ($scope.$parent.isDevice) {
      nic = {
        id: $scope.newInterface.parent.id,
        tags: $scope.newInterface.tags.map(function(tag) {
          return tag.text;
        }),
        ip_assignment: $scope.newInterface.ip_assignment,
        subnet: $scope.newInterface.subnet,
        ip_address: $scope.newInterface.ip_address
      };
      $scope.saveInterfaceLink(nic);
    } else if ($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
      // Add a link to the current interface.
      nic = {
        id: $scope.newInterface.parent.id,
        mode: $scope.newInterface.mode,
        subnet: $scope.newInterface.subnet,
        ip_address: $scope.newInterface.ip_address
      };
      $scope.saveInterfaceLink(nic);
    } else if ($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
      var params = {
        parent: $scope.newInterface.parent.id,
        vlan: $scope.newInterface.vlan.id,
        mode: $scope.newInterface.mode,
        tags: $scope.newInterface.tags.map(function(tag) {
          return tag.text;
        })
      };
      if (angular.isObject($scope.newInterface.subnet)) {
        params.subnet = $scope.newInterface.subnet.id;
        params.ip_address = $scope.newInterface.ip_address;
      }
      $scope.$parent.nodesManager
        .createVLANInterface($scope.node, params)
        .then(null, function(error) {
          // Should do something better but for now just log
          // the error.
          $log.error(error);
        });
    }

    // Add again based on the clicked option.
    if (angular.isString(type)) {
      $scope.add(type, $scope.newInterface.parent);
    } else {
      $scope.selectedMode = SELECTION_MODE.NONE;
      $scope.selectedInterfaces = [];
      $scope.newInterface = {};
    }
  };

  // Return true if the networking information cannot be edited
  // or if this interface should be disabled in the list. Only
  // returns true when in create bond mode.
  $scope.isDisabled = function() {
    if ($scope.isAllNetworkingDisabled()) {
      return true;
    } else {
      return (
        $scope.selectedMode !== SELECTION_MODE.NONE &&
        $scope.selectedMode !== SELECTION_MODE.SINGLE &&
        $scope.selectedMode !== SELECTION_MODE.MULTI
      );
    }
  };

  // Return true when a bond can be created based on the current
  // selection. Only can be done if no aliases are selected and all
  // selected interfaces are on the same VLAN.
  $scope.canCreateBond = function() {
    if ($scope.selectedMode !== SELECTION_MODE.MULTI) {
      return false;
    }
    var interfaces = getSelectedInterfaces();
    var i, vlan;
    for (i = 0; i < interfaces.length; i++) {
      var nic = interfaces[i];
      if (
        nic.type === INTERFACE_TYPE.ALIAS ||
        nic.type === INTERFACE_TYPE.BOND
      ) {
        return false;
      } else if (!angular.isObject(vlan)) {
        vlan = nic.vlan;
      } else if (vlan !== nic.vlan) {
        return false;
      }
    }
    return true;
  };

  // Return true when the create bond view is being shown.
  $scope.isShowingCreateBond = function() {
    return $scope.selectedMode === SELECTION_MODE.CREATE_BOND;
  };

  // Show the create bond view.
  $scope.showCreateBond = function() {
    $scope.clearCreateBondError();
    if (
      $scope.selectedMode === SELECTION_MODE.MULTI &&
      $scope.canCreateBond()
    ) {
      $scope.selectedMode = SELECTION_MODE.CREATE_BOND;

      var parents = getSelectedInterfaces();
      var primary = parents[0];
      var mac_address = "";
      var fabric = "";
      var vlan = {};
      var subnet = "";
      if (primary && primary.mac_address) {
        mac_address = primary.mac_address;
      }
      if (primary && primary.fabric) {
        fabric = primary.fabric;
      }
      if (primary && primary.vlan) {
        vlan = primary.vlan;
      }
      if (primary && primary.subnet) {
        subnet = primary.subnet;
      }
      $scope.newBondInterface = {
        name: getNextName("bond"),
        tags: [],
        parents: parents,
        primary: primary,
        mac_address: mac_address,
        fabric: fabric,
        vlan: vlan,
        subnet: subnet,
        bond_mode: "active-backup",
        lacpRate: "fast",
        xmitHashPolicy: "layer2",
        bond_updelay: 0,
        bond_downdelay: 0,
        bond_miimon: 100
      };
    }
  };

  // Return true if the interface has a parent that is a boot interface.
  $scope.hasBootInterface = function(nic) {
    if (!angular.isArray(nic.parents)) {
      return false;
    }
    var i;
    for (i = 0; i < nic.parents.length; i++) {
      if (nic.parents[i].is_boot) {
        return true;
      }
    }
    return false;
  };

  // Return the MAC address that should be shown as a placeholder. This
  // this is the MAC address of the primary interface.
  $scope.getInterfacePlaceholderMACAddress = function(nic) {
    if (!angular.isObject(nic.primary)) {
      return "";
    } else {
      return nic.primary.mac_address;
    }
  };

  // Return true if the user has inputed a value in the MAC address field
  // but it is invalid.
  $scope.isMACAddressInvalid = function(mac_address, invalidEmpty) {
    if (angular.isUndefined(invalidEmpty)) {
      invalidEmpty = false;
    }
    if (!angular.isString(mac_address) || mac_address === "") {
      return invalidEmpty;
    }
    return !ValidationService.validateMAC(mac_address);
  };

  // Return true when the LACR rate selection should be shown.
  $scope.showLACPRate = function() {
    if ($scope.editInterface) {
      return $scope.editInterface.bond_mode === "802.3ad";
    } else {
      return $scope.newBondInterface.bond_mode === "802.3ad";
    }
  };

  // Return true when hash policy is not fully 802.3ad compliant.
  $scope.modeAndPolicyCompliant = function() {
    if ($scope.editInterface) {
      return (
        $scope.editInterface.bond_mode === "802.3ad" &&
        ($scope.editInterface.xmitHashPolicy === "layer3+4" ||
          $scope.editInterface.xmitHashPolicy === "encap3+4")
      );
    } else {
      return (
        $scope.newBondInterface.bond_mode === "802.3ad" &&
        ($scope.newBondInterface.xmitHashPolicy === "layer3+4" ||
          $scope.newBondInterface.xmitHashPolicy === "encap3+4")
      );
    }
  };

  // Return true when the XMIT hash policy should be shown.
  $scope.showXMITHashPolicy = function() {
    if ($scope.editInterface) {
      return (
        $scope.editInterface.bond_mode === "balance-xor" ||
        $scope.editInterface.bond_mode === "802.3ad" ||
        $scope.editInterface.bond_mode === "balance-tlb"
      );
    } else {
      return (
        $scope.newBondInterface.bond_mode === "balance-xor" ||
        $scope.newBondInterface.bond_mode === "802.3ad" ||
        $scope.newBondInterface.bond_mode === "balance-tlb"
      );
    }
  };

  // Return true if cannot add the bond.
  $scope.cannotAddBond = function() {
    return (
      $scope.isInterfaceNameInvalid($scope.newBondInterface) ||
      $scope.isMACAddressInvalid($scope.newBondInterface.mac_address)
    );
  };

  // Return true if cannot edit the bond.
  $scope.cannotEditBond = function(nic) {
    return (
      $scope.isInterfaceNameInvalid(nic) ||
      $scope.isIPAddressInvalid(nic) ||
      $scope.isMACAddressInvalid(nic.mac_address, true) ||
      nic.link_speed > nic.interface_speed
    );
  };

  // Actually add the bond.
  $scope.addBond = function() {
    if ($scope.cannotAddBond()) {
      return;
    }

    $scope.isSaving = true;

    var parents = $scope.newBondInterface.parents.map(function(nic) {
      return nic.id;
    });
    var mac_address = $scope.newBondInterface.mac_address;
    if (mac_address === "") {
      mac_address = $scope.newBondInterface.primary.mac_address;
    }
    var vlan_id,
      vlan = $scope.newBondInterface.vlan;
    if (angular.isObject(vlan)) {
      vlan_id = vlan.id;
    } else if (angular.isObject($scope.newBondInterface.primary.vlan)) {
      vlan = $scope.newBondInterface.primary.vlan;
      vlan_id = vlan.id;
    } else {
      vlan_id = null;
    }
    var subnet_id,
      subnet = $scope.newBondInterface.subnet;
    if (angular.isObject(subnet)) {
      subnet_id = subnet.id;
    } else {
      subnet_id = null;
    }
    var params = {
      name: $scope.newBondInterface.name,
      mac_address: mac_address,
      tags: $scope.newBondInterface.tags.map(function(tag) {
        return tag.text;
      }),
      parents: parents,
      bond_mode: $scope.newBondInterface.bond_mode,
      bond_lacp_rate: $scope.newBondInterface.lacpRate,
      bond_xmit_hash_policy: $scope.newBondInterface.xmitHashPolicy,
      vlan: vlan_id,
      subnet: subnet_id,
      mode: $scope.newBondInterface.mode,
      ip_address: $scope.newBondInterface.ip_address,
      bond_miimon: $scope.newBondInterface.bond_miimon,
      bond_updelay: $scope.newBondInterface.bond_updelay,
      bond_downdelay: $scope.newBondInterface.bond_downdelay
    };
    $scope.$parent.nodesManager
      .createBondInterface($scope.node, params)
      .then(function() {
        // Remove the parent interfaces so that they don't show up
        // in the listing unti the new bond appears.
        var parents = $scope.newBondInterface.parents;
        angular.forEach(parents, function(parent) {
          var idx = $scope.interfaces.indexOf(parent);
          if (idx > -1) {
            $scope.interfaces.splice(idx, 1);
          }
        });
        $scope.isSaving = false;
      })
      .catch(function(error) {
        var parsedError = angular.fromJson(error);
        $scope.createBondError = parsedError[Object.keys(parsedError)[0]][0];
        $scope.isSaving = false;
      });

    // Clear the bond interface and reset the mode.
    $scope.newBondInterface = {};
    $scope.selectedInterfaces = [];
    $scope.selectedMode = SELECTION_MODE.NONE;
  };

  $scope.clearCreateBondError = function() {
    $scope.createBondError = null;
  };

  // Return true when a bridge can be created based on the current
  // selection. Only can be done if no aliases are selected and only
  // one interface is selected.
  $scope.canCreateBridge = function() {
    if ($scope.selectedMode !== SELECTION_MODE.SINGLE) {
      return false;
    }
    var nic = getSelectedInterfaces()[0];
    if (
      nic.type === INTERFACE_TYPE.ALIAS ||
      nic.type === INTERFACE_TYPE.BRIDGE
    ) {
      return false;
    }
    return true;
  };

  // Return true when the create bridge view is being shown.
  $scope.isShowingCreateBridge = function() {
    return $scope.selectedMode === SELECTION_MODE.CREATE_BRIDGE;
  };

  // Return true when the edit bridge view is being shown.
  $scope.isShowingEdit = function() {
    return $scope.selectedMode === SELECTION_MODE.EDIT;
  };

  // Toogle interfaces in edit table
  $scope.toggleInterfaces = function() {
    $scope.isShowingInterfaces = !$scope.isShowingInterfaces;
  };

  // Checks if row is correct type and id
  $scope.isCorrectInterfaceType = function(bondInterface, parents) {
    var parentIds = parents.map(function(parent) {
      return parent.id;
    });

    var parentType = parents[0].type;
    var parentFabric = parents[0].fabric;

    if (
      bondInterface.type === parentType &&
      bondInterface.fabric === parentFabric &&
      !parentIds.includes(bondInterface.id)
    ) {
      return true;
    }

    return false;
  };

  // Show the create bridge view.
  $scope.showCreateBridge = function() {
    if (
      $scope.selectedMode === SELECTION_MODE.SINGLE &&
      $scope.canCreateBridge()
    ) {
      $scope.selectedMode = SELECTION_MODE.CREATE_BRIDGE;

      var parents = getSelectedInterfaces();
      var primary = parents[0];
      var mac_address = "";
      var fabric = "";
      var vlan = {};
      if (primary && primary.mac_address) {
        mac_address = primary.mac_address;
      }
      if (primary && primary.fabric) {
        fabric = primary.fabric;
      }
      if (primary && primary.vlan) {
        vlan = primary.vlan;
      }
      $scope.newBridgeInterface = {
        name: getNextName("br"),
        tags: [],
        parents: parents,
        primary: primary,
        mac_address: mac_address,
        fabric: fabric,
        vlan: vlan,
        bridge_stp: false,
        bridge_fd: 15,
        bridge_type: "standard"
      };
    }
  };

  // Return true if cannot add the bridge.
  $scope.cannotAddBridge = function() {
    return (
      $scope.isInterfaceNameInvalid($scope.newBridgeInterface) ||
      $scope.isMACAddressInvalid($scope.newBridgeInterface.mac_address)
    );
  };

  // Actually add the bridge.
  $scope.addBridge = function() {
    if ($scope.cannotAddBridge()) {
      return;
    }

    var parents = [$scope.newBridgeInterface.primary.id];
    var mac_address = $scope.newBridgeInterface.mac_address;
    if (mac_address === "") {
      mac_address = $scope.newBridgeInterface.primary.mac_address;
    }

    var vlan_id,
      vlan = $scope.newBridgeInterface.vlan;
    if (angular.isObject(vlan)) {
      vlan_id = vlan.id;
    } else if (angular.isObject($scope.newBridgeInterface.primary.vlan)) {
      vlan = $scope.newBridgeInterface.primary.vlan;
      vlan_id = vlan.id;
    } else {
      vlan_id = null;
    }
    var subnet_id,
      subnet = $scope.newBridgeInterface.subnet;
    if (angular.isObject(subnet)) {
      subnet_id = subnet.id;
    } else {
      subnet_id = null;
    }

    var params = {
      name: $scope.newBridgeInterface.name,
      mac_address: mac_address,
      tags: $scope.newBridgeInterface.tags.map(function(tag) {
        return tag.text;
      }),
      parents: parents,
      bridge_stp: $scope.newBridgeInterface.bridge_stp,
      bridge_fd: $scope.newBridgeInterface.bridge_fd,
      bridge_type: $scope.newBridgeInterface.bridge_type,
      vlan: vlan_id,
      subnet: subnet_id,
      mode: $scope.newBridgeInterface.mode,
      ip_address: $scope.newBridgeInterface.ip_address
    };
    $scope.$parent.nodesManager
      .createBridgeInterface($scope.node, params)
      .then(null, function(error) {
        // Should do something better but for now just log
        // the error.
        $log.error(error);
      });

    // Remove the parent interface so that they don't show up
    // in the listing unti the new bond appears.
    var idx = $scope.interfaces.indexOf($scope.newBridgeInterface.primary);
    if (idx > -1) {
      $scope.interfaces.splice(idx, 1);
    }

    // Clear the bridge interface and reset the mode.
    $scope.newBridgeInterface = {};
    $scope.selectedInterfaces = [];
    $scope.selectedMode = SELECTION_MODE.NONE;
  };

  // Return true when the create physical interface view is being shown.
  $scope.isShowingCreatePhysical = function() {
    return $scope.selectedMode === SELECTION_MODE.CREATE_PHYSICAL;
  };

  // Show the create interface view.
  $scope.showCreatePhysical = function() {
    if ($scope.selectedMode === SELECTION_MODE.NONE) {
      $scope.selectedMode = SELECTION_MODE.CREATE_PHYSICAL;
      if ($scope.$parent.isDevice) {
        $scope.newInterface = {
          name: getNextName("eth"),
          mac_address: "",
          macError: false,
          tags: [],
          errorMsg: null,
          subnet: null,
          ip_assignment: IP_ASSIGNMENT.DYNAMIC
        };
      } else {
        $scope.newInterface = {
          name: getNextName("eth"),
          mac_address: "",
          macError: false,
          tags: [],
          errorMsg: null,
          fabric: $scope.fabrics[0],
          vlan: getDefaultVLAN($scope.fabrics[0]),
          subnet: null,
          mode: LINK_MODE.LINK_UP
        };
      }
    }
  };

  // Has to call parent so event can be broadcast
  $scope.validateNetworkConfiguration = () => {
    $scope.$parent.validateNetworkConfiguration();
  };

  // Return true if cannot add the interface.
  $scope.cannotAddPhysicalInterface = function() {
    return (
      $scope.isInterfaceNameInvalid($scope.newInterface) ||
      $scope.isMACAddressInvalid($scope.newInterface.mac_address, true)
    );
  };

  // Actually add the new physical interface.
  $scope.addPhysicalInterface = function() {
    if ($scope.cannotAddPhysicalInterface()) {
      return;
    }

    var params;
    if ($scope.$parent.isDevice) {
      params = {
        name: $scope.newInterface.name,
        mac_address: $scope.newInterface.mac_address,
        tags: $scope.newInterface.tags.map(function(tag) {
          return tag.text;
        }),
        ip_assignment: $scope.newInterface.ip_assignment,
        ip_address: $scope.newInterface.ip_address
      };
    } else {
      params = {
        name: $scope.newInterface.name,
        tags: $scope.newInterface.tags.map(function(tag) {
          return tag.text;
        }),
        mac_address: $scope.newInterface.mac_address,
        vlan: $scope.newInterface.vlan.id,
        mode: $scope.newInterface.mode,
        ip_address: $scope.newInterface.ip_address
      };
    }
    if (angular.isObject($scope.newInterface.subnet)) {
      params.subnet = $scope.newInterface.subnet.id;
    }
    $scope.newInterface.macError = false;
    $scope.newInterface.errorMsg = null;
    $scope.$parent.nodesManager
      .createPhysicalInterface($scope.node, params)
      .then(
        function() {
          // Clear the interface and reset the mode.
          $scope.newInterface = {};
          $scope.selectedMode = SELECTION_MODE.NONE;
        },
        function(errorStr) {
          const error = JSONService.tryParse(errorStr);
          if (!angular.isObject(error)) {
            // Was not a JSON error. This is wrong here as it
            // should be, so just log to the console, unless link_speed error
            if (errorStr.includes("link_speed")) {
              $scope.newInterface.errorMsg = errorStr;
            }
            $log.error(errorStr);
          } else {
            const macError = error.mac_address;
            if (angular.isArray(macError)) {
              $scope.newInterface.macError = true;
              $scope.newInterface.errorMsg = macError[0];
            }
          }
        }
      );
  };

  $scope.getDHCPStatus = vlan => {
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

  $scope.isChangingConnectionStatus = false;

  $scope.changeConnectionStatus = nic => {
    $scope.isChangingConnectionStatus = true;
    $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
    $scope.showEditWarning = false;
  };

  $scope.saveConnectionStatus = nic => {
    const params = $scope.preProcessInterface(angular.copy(nic));
    params.link_connected = !nic.link_connected;

    $scope.$parent.nodesManager
      .updateInterface($scope.node, nic.id, params)
      .then(() => {
        $scope.isChangingConnectionStatus = false;
        $scope.selectedInterfaces = [];
      })
      .catch(err => $log.error(err));
  };

  $scope.showEditWarning = false;
  $scope.checkIfConnected = nic => {
    if (nic.link_connected) {
      $scope.edit(nic);
    } else {
      $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
      $scope.showEditWarning = true;
    }
  };

  $scope.getNetworkTestingStatus = nic => {
    const results = $scope.networkTestingResults;
    const resultKey = `${nic.name} (${nic.mac_address})`;
    let failedTests = [];

    if (results[resultKey]) {
      failedTests = results[resultKey].filter(
        res => res.status_name === "Failed"
      );
    }

    if (failedTests.length > 1) {
      return `${failedTests.length} failed tests`;
    }

    if (failedTests.length === 1) {
      return `${failedTests[0].name} failed`;
    }

    return;
  };

  $scope.canMarkAsConnected = nic => {
    return (
      !$scope.cannotEditInterface(nic) &&
      !nic.link_connected &&
      $scope.isInterface(nic)
    );
  };

  $scope.canMarkAsDisconnected = nic => {
    return (
      !$scope.cannotEditInterface(nic) &&
      nic.link_connected &&
      $scope.isInterface(nic)
    );
  };

  $scope.formatSpeedUnits = speedInMbytes => {
    const megabytesInGigabyte = 1000;
    const gigabytesInTerabyte = 1000;

    if (!speedInMbytes || speedInMbytes < 1) {
      return "-";
    }

    if (speedInMbytes < megabytesInGigabyte) {
      return `${speedInMbytes} Mbps`;
    }

    if (
      speedInMbytes >= megabytesInGigabyte &&
      speedInMbytes < megabytesInGigabyte * gigabytesInTerabyte
    ) {
      return `${Math.round(speedInMbytes / megabytesInGigabyte)} Gbps`;
    }

    if (speedInMbytes >= megabytesInGigabyte * gigabytesInTerabyte) {
      return `${Math.round(
        speedInMbytes / megabytesInGigabyte / gigabytesInTerabyte
      )} Tbps`;
    }
  };

  // Load all the required managers. NodesManager and GeneralManager
  // are loaded by the parent controller "NodeDetailsController".
  ManagerHelperService.loadManagers($scope, [
    FabricsManager,
    VLANsManager,
    SubnetsManager,
    UsersManager,
    ControllersManager,
    DHCPSnippetsManager
  ]).then(function() {
    // GeneralManager is loaded by the parent scope however
    // bond_options may not have been loaded. If it hasn't been
    // loaded, load it.
    if (!GeneralManager.isDataLoaded("bond_options")) {
      GeneralManager.loadItems(["bond_options"]);
    }
    $scope.managersHaveLoaded = true;
    updateLoaded();
  });

  // Tell $parent that the networkingController has been loaded.
  $scope.$parent.controllerLoaded("networkingController", $scope);
}
