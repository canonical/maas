/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Networking Controller
 */

angular.module('MAAS').controller('NodeNetworkingController', [
    '$scope', 'FabricsManager', 'VLANsManager', 'SubnetsManager',
    'NodesManager', 'ManagerHelperService',
    function(
        $scope, FabricsManager, VLANsManager, SubnetsManager, NodesManager,
        ManagerHelperService) {

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

        // Set the initial values for this scope.
        $scope.loaded = false;
        $scope.nodeHasLoaded = false;
        $scope.managersHaveLoaded = false;
        $scope.column = 'name';
        $scope.fabrics = FabricsManager.getItems();
        $scope.vlans = VLANsManager.getItems();
        $scope.interfaces = [];
        $scope.interfaceLinksMap = {};
        $scope.originalInterfaces = {};
        $scope.showingMembers = [];
        $scope.focusInterface = null;

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
                    nic.subnet_id = null;
                    nic.mode = LINK_MODE.LINK_UP;
                    nic.ip_address = "";
                    interfaces.push(nic);
                } else {
                    var idx = 0;
                    angular.forEach(nic.links, function(link) {
                        var nic_copy = angular.copy(nic);
                        nic_copy.link_id = link.id;
                        nic_copy.subnet_id = link.subnet_id;
                        nic_copy.mode = link.mode;
                        nic_copy.ip_address = link.ip_address;
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
        }

        // Called by $parent when the node has been loaded.
        $scope.nodeLoaded = function() {
            $scope.$watch("node.interfaces", updateInterfaces);
            $scope.nodeHasLoaded = true;
            updateLoaded();
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

        // Get the subnet for the interface.
        $scope.getSubnet = function(nic) {
            return SubnetsManager.getItemFromList(nic.subnet_id);
        };

        // Get the name of the subnet for this interface.
        $scope.getSubnetName = function(nic) {
            if(angular.isNumber(nic.subnet_id)) {
                var subnet = $scope.getSubnet(nic);
                if(angular.isObject(subnet)) {
                    return subnet.name;
                } else {
                    return "Unknown";
                }
            } else {
                return "Unconfigured";
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
            // If the name or vlan has changed then we need to update
            // the interface.
            var originalInteface = $scope.originalInterfaces[nic.id];
            if(originalInteface.name !== nic.name ||
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
                $scope.saveInterface($scope.focusInterface);
                $scope.focusInterface = null;
            } else if($scope.focusInterface === nic) {
                $scope.saveInterface($scope.focusInterface);
                $scope.focusInterface = null;
            }
        };

        // Return True if the interface name that the user typed is invalid.
        $scope.isInterfaceNameInvalid = function(nic) {
            if(nic.name.length === 0) {
                return true;
            } else {
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
            nic.vlan = VLANsManager.getItemFromList(nic.fabric.vlan_ids[0]);
            $scope.saveInterface(nic);
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            FabricsManager,
            VLANsManager,
            SubnetsManager
        ]).then(function() {
            $scope.managersHaveLoaded = true;
            updateLoaded();
        });
    }]);
