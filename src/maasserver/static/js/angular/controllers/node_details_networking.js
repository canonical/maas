/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Networking Controller
 */

// Filter that is specific to the NodeNetworkingController. Filters the
// list of VLANs to be only those that are unused by the interface.
angular.module('MAAS').filter('filterByUnusedForInterface', function() {
    return function(vlans, nic, originalInterfaces) {
        var filtered = [];
        if(!angular.isObject(nic) ||
            !angular.isObject(originalInterfaces)) {
            return filtered;
        }
        var usedVLANs = [];
        angular.forEach(originalInterfaces, function(inter) {
            if(inter.type === "vlan") {
                var parent = inter.parents[0];
                if(parent === nic.id) {
                    usedVLANs.push(inter.vlan_id);
                }
            }
        });
        angular.forEach(vlans, function(vlan) {
            var idx = usedVLANs.indexOf(vlan.id);
            if(idx === -1) {
                filtered.push(vlan);
            }
        });
        return filtered;
    };
});


// Filter that is specific to the NodeNetworkingController. Filters the
// list of interfaces to not include the current parent interfaces being
// bonded together.
angular.module('MAAS').filter('removeBondParents', function() {
    return function(interfaces, bondInterface) {
        if(!angular.isObject(bondInterface) ||
            !angular.isArray(bondInterface.parents)) {
            return interfaces;
        }
        var filtered = [];
        angular.forEach(interfaces, function(nic) {
            var i, parent, found = false;
            for(i = 0; i < bondInterface.parents.length; i++) {
                parent = bondInterface.parents[i];
                if(parent.id === nic.id && parent.link_id === nic.link_id) {
                    found = true;
                    break;
                }
            }
            if(!found) {
                filtered.push(nic);
            }
        });
        return filtered;
    };
});


// Filter that is specific to the NodeNetworkingController. Remove the default
// VLAN if the interface is a VLAN interface.
angular.module('MAAS').filter('removeDefaultVLANIfVLAN', function() {
    return function(vlans, interfaceType) {
        if(!angular.isString(interfaceType)) {
            return vlans;
        }
        var filtered = [];
        angular.forEach(vlans, function(vlan) {
            if(interfaceType !== "vlan") {
                filtered.push(vlan);
            } else if(vlan.vid !== 0) {
                filtered.push(vlan);
            }
        });
        return filtered;
    };
});


// Filter that is specific to the NodeNetworkingController. Only provide the
// available modes for that interface type.
angular.module('MAAS').filter('filterLinkModes', function() {
    return function(modes, nic) {
        if(!angular.isObject(nic)) {
            return modes;
        }
        var filtered = [];
        if(!angular.isObject(nic.subnet)) {
            // No subnet is configure so the only allowed mode
            // is 'link_up'.
            angular.forEach(modes, function(mode) {
                if(mode.mode === "link_up") {
                    filtered.push(mode);
                }
            });
        } else {
            // Don't add LINK_UP  or DHCP if more than one link exists or
            // if the interface is an alias.
            var allowLinkUpAndDHCP = (
                (angular.isObject(nic.links) && nic.links.length > 1) ||
                (nic.type === "alias"));
            angular.forEach(modes, function(mode) {
                if(allowLinkUpAndDHCP && (
                    mode.mode === "link_up" ||
                    mode.mode === "dhcp")) {
                    return;
                }
                filtered.push(mode);
            });
        }
        return filtered;
    };
});


angular.module('MAAS').controller('NodeNetworkingController', [
    '$scope', '$filter', 'FabricsManager', 'VLANsManager', 'SubnetsManager',
    'NodesManager', 'GeneralManager', 'UsersManager', 'ManagerHelperService',
    'ValidationService',
    function(
        $scope, $filter, FabricsManager, VLANsManager, SubnetsManager,
        NodesManager, GeneralManager, UsersManager, ManagerHelperService,
        ValidationService) {

        // Different interface types.
        var INTERFACE_TYPE = {
            PHYSICAL: "physical",
            BOND: "bond",
            VLAN: "vlan",
            ALIAS: "alias"
        };
        var INTERFACE_TYPE_TEXTS = {
            "physical": "Physical",
            "bond": "Bond",
            "vlan": "VLAN",
            "alias": "Alias"
        };

        // Different link modes for an interface.
        var LINK_MODE = {
            AUTO: "auto",
            STATIC: "static",
            DHCP: "dhcp",
            LINK_UP: "link_up"
        };
        var LINK_MODE_TEXTS = {
            "auto": "Auto assign",
            "static": "Static assign",
            "dhcp": "DHCP",
            "link_up": "Unconfigured"
        };

        // Different selection modes.
        var SELECTION_MODE = {
            NONE: null,
            SINGLE: "single",
            MULTI: "multi",
            DELETE: "delete",
            ADD: "add",
            CREATE_BOND: "create-bond"
        };

        // Set the initial values for this scope.
        $scope.loaded = false;
        $scope.nodeHasLoaded = false;
        $scope.managersHaveLoaded = false;
        $scope.column = 'name';
        $scope.fabrics = FabricsManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.subnets = SubnetsManager.getItems();
        $scope.interfaces = [];
        $scope.interfaceLinksMap = {};
        $scope.originalInterfaces = {};
        $scope.showingMembers = [];
        $scope.focusInterface = null;
        $scope.selectedInterfaces = [];
        $scope.selectedMode = null;
        $scope.newInterface = {};
        $scope.newBondInterface = {};
        $scope.bondOptions = GeneralManager.getData("bond_options");
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

        // Give $parent which is the NodeDetailsController access to this scope
        // it will call `nodeLoaded` once the node has been fully loaded.
        $scope.$parent.networkingController = $scope;

        // Sets loaded to true if both the node has been loaded at the
        // other required managers for this scope have been loaded.
        function updateLoaded() {
            $scope.loaded = $scope.nodeHasLoaded && $scope.managersHaveLoaded;
            if($scope.loaded) {
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
            angular.forEach($scope.node.interfaces, function(nic) {
                // When a interface has a child that is a bond. Then that
                // interface is not included in the interface list. Parent
                // interface with a bond child can only have one child.
                if(nic.children.length === 1) {
                    var child = $scope.originalInterfaces[nic.children[0]];
                    if(child.type === INTERFACE_TYPE.BOND) {
                        // This parent now has a bond for a child, if this was
                        // the focusInterface then the focus needs to be
                        // removed. We only need to check the "id" not the
                        // "link_id", because if this interface did have
                        // aliases they have now been removed.
                        if(angular.isObject($scope.focusInterface) &&
                            $scope.focusInterface.id === nic.id) {
                            $scope.focusInterface = null;
                        }
                        return;
                    }
                }

                // When the interface is a bond, place the children as members
                // for that interface.
                if(nic.type === INTERFACE_TYPE.BOND) {
                    nic.members = [];
                    angular.forEach(nic.parents, function(parent) {
                        nic.members.push(
                            angular.copy($scope.originalInterfaces[parent]));
                    });
                }

                // Add the VLAN and fabric to the interface.
                nic.vlan = VLANsManager.getItemFromList(nic.vlan_id);
                if(angular.isObject(nic.vlan)) {
                    nic.fabric = FabricsManager.getItemFromList(
                        nic.vlan.fabric);
                }

                // Update the interface based on its links or duplicate the
                // interface if it has multiple links.
                if(nic.links.length === 0) {
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
                        nic_copy.subnet = SubnetsManager.getItemFromList(
                            link.subnet_id);
                        nic_copy.mode = link.mode;
                        nic_copy.ip_address = link.ip_address;
                        if(angular.isUndefined(nic_copy.ip_address)) {
                            nic_copy.ip_address = "";
                        }
                        // We don't want to deep copy the VLAN and fabric
                        // object so we set those back to the original.
                        nic_copy.vlan = nic.vlan;
                        nic_copy.fabric = nic.fabric;
                        if(idx > 0) {
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

            // Update the scope interface links mapping.
            $scope.interfaceLinksMap = {};
            angular.forEach($scope.interfaces, function(nic) {
                var linkMaps = $scope.interfaceLinksMap[nic.id];
                if(angular.isUndefined(linkMaps)) {
                    linkMaps = {};
                    $scope.interfaceLinksMap[nic.id] = linkMaps;
                }
                linkMaps[nic.link_id] = nic;
            });

            // Clear the focusInterface if it no longer exists in the
            // interfaceLinksMap.
            if(angular.isObject($scope.focusInterface)) {
                var links = $scope.interfaceLinksMap[$scope.focusInterface.id];
                if(angular.isUndefined(links)) {
                    $scope.focusInterface = null;
                } else {
                    var link = links[$scope.focusInterface.link_id];
                    if(angular.isUndefined(link)) {
                        $scope.focusInterface = null;
                    }
                }
            }

            // Update newInterface.parent if it has changed.
            updateNewInterface();
        }

        // Return the original link object for the given interface.
        function mapNICToOriginalLink(nic) {
            var originalInteface = $scope.originalInterfaces[nic.id];
            if(angular.isObject(originalInteface)) {
                var i, link = null;
                for(i = 0; i < originalInteface.links.length; i++) {
                    link = originalInteface.links[i];
                    if(link.id === nic.link_id) {
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
            if($scope.selectedMode === SELECTION_MODE.SINGLE ||
                $scope.selectedMode === SELECTION_MODE.ADD ||
                $scope.selectedMode === SELECTION_MODE.DELETE) {
                $scope.selectedMode = SELECTION_MODE.NONE;
            }
        }

        // Update the new interface since the interfaces list has
        // been reloaded.
        function updateNewInterface() {
            if(angular.isObject($scope.newInterface.parent)) {
                var parentId = $scope.newInterface.parent.id;
                var linkId = $scope.newInterface.parent.link_id;
                var links = $scope.interfaceLinksMap[parentId];
                if(angular.isObject(links)) {
                    var newParent = links[linkId];
                    if(angular.isObject(newParent)) {
                        $scope.newInterface.parent = newParent;

                        var iType = $scope.newInterface.type;
                        var isAlias = iType === INTERFACE_TYPE.ALIAS;
                        var isVLAN = iType === INTERFACE_TYPE.VLAN;
                        var canAddAlias = $scope.canAddAlias(newParent);
                        var canAddVLAN = $scope.canAddVLAN(newParent);
                        if(!canAddAlias && !canAddVLAN) {
                            // Cannot do any adding now.
                            $scope.newInterface = {};
                            leaveSingleSelectionMode();
                        } else {
                            if(isAlias && !canAddAlias && canAddVLAN) {
                                $scope.newInterface.type = "vlan";
                                $scope.addTypeChanged();
                            } else if(isVLAN && !canAddVLAN && canAddAlias) {
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
            return VLANsManager.getItemFromList(fabric.vlan_ids[0]);
        }

        // Return list of unused VLANs for an interface. Also remove the
        // ignoreVLANs from the returned list.
        function getUnusedVLANs(nic, ignoreVLANs) {
            var vlans = $filter('removeDefaultVLAN')($scope.vlans);
            vlans = $filter('filterByFabric')(vlans, nic.fabric);
            vlans = $filter('filterByUnusedForInterface')(
                vlans, nic, $scope.originalInterfaces);

            // Remove the VLAN's that should be ignored when getting the unused
            // VLANs. This is done to help the selection of the next default.
            if(angular.isUndefined(ignoreVLANs)) {
                ignoreVLANs = [];
            }
            angular.forEach(ignoreVLANs, function(vlan) {
                var i;
                for(i = 0; i < vlans.length; i++) {
                    if(vlans[i].id === vlan.id) {
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
                var splitKey = key.split('/');
                var links = $scope.interfaceLinksMap[splitKey[0]];
                if(angular.isObject(links)) {
                    var nic = links[splitKey[1]];
                    if(angular.isObject(nic)) {
                        interfaces.push(nic);
                    }
                }
            });
            return interfaces;
        }

        // Get the next available bond name.
        function getNextBondName() {
            var idx = 0;
            angular.forEach($scope.originalInterfaces, function(nic) {
                if(nic.name === "bond" + idx) {
                    idx++;
                }
            });
            return "bond" + idx;
        }

        // Called by $parent when the node has been loaded.
        $scope.nodeLoaded = function() {
            $scope.$watch("node.interfaces", updateInterfaces);
            $scope.nodeHasLoaded = true;
            updateLoaded();
        };

        // Return true if user is a super user/
        $scope.isSuperUser = function() {
            var authUser = UsersManager.getAuthUser();
            if(!angular.isObject(authUser)) {
                return false;
            }
            return authUser.is_superuser;
        };

        // Return true if the networking information cannot be edited.
        // (it can't be changed when the node is in any state other
        // than Ready or Broken and the user is not a superuser)
        $scope.isAllNetworkingDisabled = function() {
            if (!$scope.isSuperUser()) {
                // If the user is not a superuser, disable the networking panel.
                return true;
            } else if (angular.isObject($scope.node) &&
                ["Ready", "Broken"].indexOf($scope.node.status) === -1) {
                // If the node is not ready or broken, disable networking panel.
                return true;
            } else {
                // User must be a superuser and the node must be
                // either ready or broken. Enable it.
                return false;
            }
        };

        // Get the text for the type of the interface.
        $scope.getInterfaceTypeText = function(nic) {
            var text = INTERFACE_TYPE_TEXTS[nic.type];
            if(angular.isDefined(text)) {
                return text;
            } else {
                return nic.type;
            }
        };

        // Get the text for the link mode of the interface.
        $scope.getLinkModeText = function(nic) {
            var text = LINK_MODE_TEXTS[nic.mode];
            if(angular.isDefined(text)) {
                return text;
            } else {
                return nic.mode;
            }
        };

        // Get the text to display in the VLAN dropdown.
        $scope.getVLANText = function(vlan) {
            if(!angular.isObject(vlan)) {
                return "";
            }

            if(vlan.vid === 0) {
                return "untagged";
            } else if(angular.isString(vlan.name) && vlan.name.length > 0) {
                return vlan.vid + " (" + vlan.name + ")";
            } else {
                return vlan.vid;
            }
        };

        // Get the text to display in the subnet dropdown.
        $scope.getSubnetText = function(subnet) {
            if(!angular.isObject(subnet)) {
                return "Unconfigured";
            } else if(angular.isString(subnet.name) &&
                subnet.name.length > 0 &&
                subnet.cidr !== subnet.name) {
                return subnet.cidr + " (" + subnet.name + ")";
            } else {
                return subnet.cidr;
            }
        };

        // Toggle showing or hiding the members of the interface.
        $scope.toggleMembers = function(nic) {
            var idx = $scope.showingMembers.indexOf(nic.id);
            if(idx === -1) {
                $scope.showingMembers.push(nic.id);
            } else {
                $scope.showingMembers.splice(idx, 1);
            }
        };

        // Return True when the interface is showing its members section.
        $scope.isShowingMembers = function(nic) {
            return $scope.showingMembers.indexOf(nic.id) > -1;
        };

        // Save the following interface on the node. This will only save if
        // the interface has changed.
        $scope.saveInterface = function(nic) {
            var originalInteface = $scope.originalInterfaces[nic.id];
            if($scope.isInterfaceNameInvalid(nic)) {
                nic.name = originalInteface.name;
            } else if(originalInteface.name !== nic.name ||
                originalInteface.vlan_id !== nic.vlan.id) {
                var params = {
                    "name": nic.name,
                    "vlan": nic.vlan.id
                };
                NodesManager.updateInterface($scope.node, nic.id, params).then(
                    null, function(error) {
                        // XXX blake_r: Just log the error in the console, but
                        // we need to expose this as a better message to the
                        // user.
                        console.log(error);

                        // Update the interfaces so it is back to the way it
                        // was before the user changed it.
                        updateInterfaces();
                    });
            }
        };

        // Set the focus to this interface.
        $scope.setFocusInterface = function(nic) {
            $scope.focusInterface = nic;
        };

        // Clear the current focused interface. This will save the interface
        // if it has changed.
        $scope.clearFocusInterface = function(nic) {
            if(angular.isUndefined(nic)) {
                if($scope.focusInterface.type !== INTERFACE_TYPE.ALIAS) {
                    $scope.saveInterface($scope.focusInterface);
                }
                $scope.saveInterfaceIPAddress($scope.focusInterface);
                $scope.focusInterface = null;
            } else if($scope.focusInterface === nic) {
                if($scope.focusInterface.type !== INTERFACE_TYPE.ALIAS) {
                    $scope.saveInterface($scope.focusInterface);
                }
                $scope.saveInterfaceIPAddress($scope.focusInterface);
                $scope.focusInterface = null;
            }
        };

        // Return True if the interface name that the user typed is invalid.
        $scope.isInterfaceNameInvalid = function(nic) {
            if(!angular.isString(nic.name) || nic.name.length === 0) {
                return true;
            } else if(angular.isArray($scope.node.interfaces)) {
                var i;
                for(i = 0; i < $scope.node.interfaces.length; i++) {
                    var otherNic = $scope.node.interfaces[i];
                    if(otherNic.name === nic.name && otherNic.id !== nic.id) {
                        return true;
                    }
                }
            }
            return false;
        };

        // Called when the fabric dropdown is changed.
        $scope.fabricChanged = function(nic) {
            // Update the VLAN on the node to be the default VLAN for that
            // fabric. The first VLAN for the fabric is the default.
            nic.vlan = getDefaultVLAN(nic.fabric);
            $scope.saveInterface(nic);
        };

        // Return True if the link mode select should be disabled.
        $scope.isLinkModeDisabled = function(nic) {
            // This is only disabled when a subnet has not been selected.
            return !angular.isObject(nic.subnet);
        };

        // Called when the link mode for this interface and link has been
        // changed.
        $scope.saveInterfaceLink = function(nic) {
            var params = {
                "mode": nic.mode
            };
            if(angular.isObject(nic.subnet)) {
                params.subnet = nic.subnet.id;
            }
            if(angular.isDefined(nic.link_id) && nic.link_id >= 0) {
                params.link_id = nic.link_id;
            }
            if(nic.mode === LINK_MODE.STATIC && nic.ip_address.length > 0) {
                params.ip_address = nic.ip_address;
            }
            return NodesManager.linkSubnet($scope.node, nic.id, params).then(
                null, function(error) {
                    // XXX blake_r: Just log the error in the console, but
                    // we need to expose this as a better message to the
                    // user.
                    console.log(error);

                    // Update the interfaces so it is back to the way it
                    // was before the user changed it.
                    updateInterfaces();
                });
        };

        // Called when the user changes the subnet.
        $scope.subnetChanged = function(nic) {
            if(!angular.isObject(nic.subnet)) {
                // Set to 'Unconfigured' so the link mode should be set to
                // 'link_up'.
                nic.mode = LINK_MODE.LINK_UP;
            }
            // Clear the IP address so a new one on the subnet is assigned.
            nic.ip_address = "";
            $scope.saveInterfaceLink(nic);
        };

        // Return True when the IP address input field should be shown.
        $scope.shouldShowIPAddress = function(nic) {
            if(nic.mode === LINK_MODE.STATIC) {
                // Check that the original has an IP address if it doesn't then
                // it should not be shown as the IP address still has not been
                // loaded over the websocket. If the subnets have been switched
                // then the IP address has been clear, don't show the IP
                // address until the original subnet and nic subnet match.
                var originalLink = mapNICToOriginalLink(nic);
                return (
                    angular.isObject(originalLink) &&
                    angular.isString(originalLink.ip_address) &&
                    originalLink.ip_address.length > 0 &&
                    angular.isObject(nic.subnet) &&
                    nic.subnet.id === originalLink.subnet_id);
            } else if(angular.isString(nic.ip_address) &&
                nic.ip_address.length > 0) {
                return true;
            } else {
                return false;
            }
        };

        // Return True if the interface IP address that the user typed is
        // invalid.
        $scope.isIPAddressInvalid = function(nic) {
            return (!angular.isString(nic.ip_address) ||
                nic.ip_address.length === 0 ||
                !ValidationService.validateIP(nic.ip_address) ||
                !ValidationService.validateIPInNetwork(
                    nic.ip_address, nic.subnet.cidr));
        };

        // Save the interface IP address.
        $scope.saveInterfaceIPAddress = function(nic) {
            var originalLink = mapNICToOriginalLink(nic);
            var prevIPAddress = originalLink.ip_address;
            if($scope.isIPAddressInvalid(nic)) {
                nic.ip_address = prevIPAddress;
            } else if(nic.ip_address !== prevIPAddress) {
                $scope.saveInterfaceLink(nic);
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
            if(idx > -1) {
                $scope.selectedInterfaces.splice(idx, 1);
            } else {
                $scope.selectedInterfaces.push(key);
            }

            if($scope.selectedInterfaces.length > 1) {
                if($scope.selectedMode !== SELECTION_MODE.BOND) {
                    $scope.selectedMode = SELECTION_MODE.MULTI;
                }
            } else if($scope.selectedInterfaces.length === 1) {
                $scope.selectedMode = SELECTION_MODE.SINGLE;
            } else {
                $scope.selectedMode = SELECTION_MODE.NONE;
            }
        };

        // Return true when the interface is selected.
        $scope.isInterfaceSelected = function(nic) {
            return $scope.selectedInterfaces.indexOf(
                $scope.getUniqueKey(nic)) > -1;
        };

        // Return true if this is the only interface selected.
        $scope.isOnlyInterfaceSelected = function(nic) {
            if($scope.selectedInterfaces.length === 1) {
                var key = $scope.getUniqueKey(nic);
                return $scope.selectedInterfaces[0] === key;
            } else {
                return false;
            }
        };

        // Return true if the interface options is being shown.
        $scope.isShowingInterfaceOptions = function() {
            return $scope.selectedMode === SELECTION_MODE.SINGLE;
        };

        // Return true if the interface delete confirm is being shown.
        $scope.isShowingDeleteComfirm = function() {
            return $scope.selectedMode === SELECTION_MODE.DELETE;
        };

        // Return true if the interface add interface is being shown.
        $scope.isShowingAdd = function() {
            return $scope.selectedMode === SELECTION_MODE.ADD;
        };

        // Return true if the alias can be added to interface.
        $scope.canAddAlias = function(nic) {
            if(!angular.isObject(nic)) {
                return false;
            } else if(nic.type === INTERFACE_TYPE.ALIAS) {
                return false;
            } else if(nic.links.length === 0 ||
                nic.links[0].mode === LINK_MODE.LINK_UP ||
                nic.links[0].mode === LINK_MODE.DHCP) {
                return false;
            } else {
                return true;
            }
        };

        // Return true if the VLAN can be added to interface.
        $scope.canAddVLAN = function(nic) {
            if(!angular.isObject(nic)) {
                return false;
            } else if(nic.type === INTERFACE_TYPE.ALIAS ||
                nic.type === INTERFACE_TYPE.VLAN) {
                return false;
            }
            var unusedVLANs = getUnusedVLANs(nic);
            return unusedVLANs.length > 0;
        };

        // Return true if another VLAN can be added to this already being
        // added interface.
        $scope.canAddAnotherVLAN = function(nic) {
            if(!$scope.canAddVLAN(nic)) {
                return false;
            }
            var unusedVLANs = getUnusedVLANs(nic);
            return unusedVLANs.length > 1;
        };

        // Return the text to use for the remove link and message.
        $scope.getRemoveTypeText = function(nic) {
            if(nic.type === INTERFACE_TYPE.PHYSICAL) {
                return "interface";
            } else if(nic.type === INTERFACE_TYPE.VLAN) {
                return "VLAN";
            } else {
                return nic.type;
            }
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
            $scope.newInterface = {};
            $scope.newBondInterface = {};
            if($scope.selectedMode === SELECTION_MODE.CREATE_BOND) {
                $scope.selectedMode = SELECTION_MODE.MULTI;
            } else {
                $scope.selectedMode = SELECTION_MODE.SINGLE;
            }
        };

        // Confirm the removal of interface.
        $scope.confirmRemove = function(nic) {
            $scope.selectedMode = SELECTION_MODE.NONE;
            $scope.selectedInterfaces = [];
            if(nic.type !== INTERFACE_TYPE.ALIAS) {
                NodesManager.deleteInterface($scope.node, nic.id);
            } else {
                NodesManager.unlinkSubnet($scope.node, nic.id, nic.link_id);
            }

            // Remove the interface from available interfaces
            var idx = $scope.interfaces.indexOf(nic);
            if(idx > -1) {
                $scope.interfaces.splice(idx, 1);
            }
        };

        // Enter add mode.
        $scope.add = function(type, nic) {
            // When this is called right after another VLAN was just added, we
            // remove its used VLAN from the available list.
            var ignoreVLANs = [];
            if(angular.isObject($scope.newInterface.vlan)) {
                ignoreVLANs.push($scope.newInterface.vlan);
            }

            // Get the default VLAN for the new interface.
            var vlans = getUnusedVLANs(nic, ignoreVLANs);
            var defaultVLAN = null;
            if(vlans.length > 0) {
                defaultVLAN = vlans[0];
            }
            var defaultSubnet = null;
            var defaultMode = LINK_MODE.LINK_UP;

            // Alias used defaults based from its parent.
            if(type === INTERFACE_TYPE.ALIAS) {
                defaultVLAN = nic.vlan;
                defaultSubnet = VLANsManager.getSubnets(defaultVLAN)[0];
                defaultMode = LINK_MODE.AUTO;
            }

            // Setup the new interface and enter add mode.
            $scope.newInterface = {
                type: type,
                vlan: defaultVLAN,
                subnet: defaultSubnet,
                mode: defaultMode,
                parent: nic
            };
            $scope.selectedMode = SELECTION_MODE.ADD;
        };

        // Quickly enter add by selecting the node first.
        $scope.quickAdd = function(nic) {
            $scope.selectedInterfaces = [$scope.getUniqueKey(nic)];
            var type = 'alias';
            if(!$scope.canAddAlias(nic)) {
                type = 'vlan';
            }
            $scope.add(type, nic);
        };

        // Return the name of the interface being added.
        $scope.getAddName = function() {
            if($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
                var aliasIdx = $scope.newInterface.parent.links.length;
                return $scope.newInterface.parent.name + ":" + aliasIdx;
            } else if ($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
                return (
                    $scope.newInterface.parent.name + "." +
                    $scope.newInterface.vlan.vid);
            }
        };

        // Called when the type of interface is changed.
        $scope.addTypeChanged = function() {
            if($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
                $scope.newInterface.vlan = $scope.newInterface.parent.vlan;
                $scope.newInterface.subnet = VLANsManager.getSubnets(
                    $scope.newInterface.vlan)[0];
                $scope.newInterface.mode = LINK_MODE.AUTO;
            } else if($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
                var vlans = getUnusedVLANs($scope.newInterface.parent);
                $scope.newInterface.vlan = null;
                if(vlans.length > 0) {
                    $scope.newInterface.vlan = vlans[0];
                }
                $scope.newInterface.subnet = null;
                $scope.newInterface.mode = LINK_MODE.LINK_UP;
            }
        };

        // Called when the VLAN is changed.
        $scope.addVLANChanged = function() {
            $scope.newInterface.subnet = null;
        };

        // Called when the subnet is changed.
        $scope.addSubnetChanged = function() {
            if(!angular.isObject($scope.newInterface.subnet)) {
                $scope.newInterface.mode = LINK_MODE.LINK_UP;
            }
        };

        // Perform the add action over the websocket.
        $scope.addInterface = function(type) {
            if($scope.newInterface.type === INTERFACE_TYPE.ALIAS) {
                // Add a link to the current interface.
                var nic = {
                    id: $scope.newInterface.parent.id,
                    mode: $scope.newInterface.mode,
                    subnet: $scope.newInterface.subnet,
                    ip_address: ""
                };
                $scope.saveInterfaceLink(nic);
            } else if($scope.newInterface.type === INTERFACE_TYPE.VLAN) {
                var params = {
                    parent: $scope.newInterface.parent.id,
                    vlan: $scope.newInterface.vlan.id,
                    mode: $scope.newInterface.mode
                };
                if(angular.isObject($scope.newInterface.subnet)) {
                    params.subnet = $scope.newInterface.subnet.id;
                }
                NodesManager.createVLANInterface($scope.node, params).then(
                    null, function(error) {
                        // Should do something better but for now just log
                        // the error.
                        console.log(error);
                    });
            }

            // Add again based on the clicked option.
            if(angular.isString(type)) {
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
                    $scope.selectedMode !== SELECTION_MODE.MULTI);
            }
        };

        // Return true when a bond can be created based on the current
        // selection. Only can be done if no aliases are selected and all
        // selected interfaces are on the same VLAN.
        $scope.canCreateBond = function() {
            if($scope.selectedMode !== SELECTION_MODE.MULTI) {
                return false;
            }
            var interfaces = getSelectedInterfaces();
            var i, vlan;
            for(i = 0; i < interfaces.length; i++) {
                var nic = interfaces[i];
                if(nic.type === INTERFACE_TYPE.ALIAS ||
                    nic.type === INTERFACE_TYPE.BOND) {
                    return false;
                } else if(!angular.isObject(vlan)) {
                    vlan = nic.vlan;
                } else if(vlan !== nic.vlan) {
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
            if($scope.selectedMode === SELECTION_MODE.MULTI &&
                $scope.canCreateBond()) {
                $scope.selectedMode = SELECTION_MODE.CREATE_BOND;

                var parents = getSelectedInterfaces();
                $scope.newBondInterface = {
                    name: getNextBondName(),
                    parents: parents,
                    primary: parents[0],
                    macAddress: "",
                    mode: "active-backup",
                    lacpRate: "slow",
                    xmitHashPolicy: "layer2"
                };
            }
        };

        // Return the MAC address that should be shown as a placeholder. This
        // this is the MAC address of the primary interface.
        $scope.getBondPlaceholderMACAddress = function() {
            if(!angular.isObject($scope.newBondInterface.primary)) {
                return "";
            } else {
                return $scope.newBondInterface.primary.mac_address;
            }
        };

        // Return true if the user has inputed a value in the MAC address field
        // but it is invalid.
        $scope.isBondMACAddressInvalid = function() {
            if(!angular.isString($scope.newBondInterface.macAddress) ||
                $scope.newBondInterface.macAddress === "") {
                return false;
            }
            return !ValidationService.validateMAC(
                $scope.newBondInterface.macAddress);
        };

        // Return true when the LACR rate selection should be shown.
        $scope.showLACPRate = function() {
            return $scope.newBondInterface.mode === "802.3ad";
        };

        // Return true when the XMIT hash policy should be shown.
        $scope.showXMITHashPolicy = function() {
            return (
                $scope.newBondInterface.mode === "balance-xor" ||
                $scope.newBondInterface.mode === "802.3ad" ||
                $scope.newBondInterface.mode === "balance-tlb");
        };

        // Actually add the bond.
        $scope.addBond = function() {
            var parents = $scope.newBondInterface.parents.map(
                function(nic) { return nic.id; });
            var macAddress = $scope.newBondInterface.macAddress;
            if(macAddress === "") {
                macAddress = $scope.newBondInterface.primary.mac_address;
            }
            var params = {
                name: $scope.newBondInterface.name,
                mac_address: macAddress,
                parents: parents,
                vlan: $scope.newBondInterface.primary.vlan.id,
                bond_mode: $scope.newBondInterface.mode,
                bond_lacp_rate: $scope.newBondInterface.lacpRate,
                bond_xmit_hash_policy: $scope.newBondInterface.xmitHashPolicy
            };
            NodesManager.createBondInterface($scope.node, params).then(
                null, function(error) {
                    // Should do something better but for now just log
                    // the error.
                    console.log(error);
                });

            // Remove the parent interfaces so that they don't show up
            // in the listing unti the new bond appears.
            angular.forEach($scope.newBondInterface.parents, function(parent) {
                var idx = $scope.interfaces.indexOf(parent);
                if(idx > -1) {
                    $scope.interfaces.splice(idx, 1);
                }
            });

            // Clear the bond interface and reset the mode.
            $scope.newBondInterface = {};
            $scope.selectedInterfaces = [];
            $scope.selectedMode = SELECTION_MODE.NONE;
        };

        // Load all the required managers. NodesManager and GeneralManager are
        // loaded by the parent controller "NodeDetailsController".
        ManagerHelperService.loadManagers([
            FabricsManager,
            VLANsManager,
            SubnetsManager,
            UsersManager
        ]).then(function() {
            $scope.managersHaveLoaded = true;
            updateLoaded();
        });
    }]);
