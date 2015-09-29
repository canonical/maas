/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Networking Controller
 */

angular.module('MAAS').controller('NodeNetworkingController', [
    '$scope', 'FabricsManager', 'VLANsManager', 'SubnetsManager',
    'ManagerHelperService',
    function(
        $scope, FabricsManager, VLANsManager, SubnetsManager,
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
        $scope.interfaces = [];
        $scope.showingMembers = [];

        // Give $parent which is the NodeDetailsController access to this scope
        // it will call `nodeLoaded` once the node has been fully loaded.
        $scope.$parent.networkingController = $scope;

        // Sets loaded to true if both the node has been loaded at the
        // other required managers for this scope have been loaded.
        function updateLoaded() {
            $scope.loaded = $scope.nodeHasLoaded && $scope.managersHaveLoaded;
        }

        // Returns a list of interfaces for the node. For each link on the
        // interface, the interface is duplicated in the list to make render
        // in a data-ng-repeat easier.
        function getInterfaces() {
            var interfaceMap = {};
            angular.forEach($scope.node.interfaces, function(nic) {
                interfaceMap[nic.id] = nic;
            });

            var interfaces = [];
            angular.forEach($scope.node.interfaces, function(nic) {
                // When a interface has a child that is a bond. Then that
                // interface is not included in the interface list. Parent
                // interface with a bond child can only have one child.
                if(nic.children.length === 1) {
                    var child = interfaceMap[nic.children[0]];
                    if(child.type === INTERFACE_TYPE.BOND) {
                        return;
                    }
                }

                // When the interface is a bond, place the children as members
                // for that interface.
                if(nic.type === INTERFACE_TYPE.BOND) {
                    nic.members = [];
                    angular.forEach(nic.parents, function(parent) {
                        nic.members.push(angular.copy(interfaceMap[parent]));
                    });
                }

                if(nic.links.length === 0) {
                    // No links on this interface. The interface is either
                    // disabled or has no links (which means the interface
                    // is in LINK_UP mode).
                    nic = angular.copy(nic);
                    nic.subnet_id = null;
                    nic.mode = LINK_MODE.LINK_UP;
                    nic.ip_address = "";
                    interfaces.push(nic);
                } else {
                    var idx = 0;
                    angular.forEach(nic.links, function(link) {
                        var nic_copy = angular.copy(nic);
                        nic_copy.subnet_id = link.subnet_id;
                        nic_copy.mode = link.mode;
                        nic_copy.ip_address = link.ip_address;
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
            return interfaces;
        }

        // Updates the interfaces list.
        function updateInterfaces() {
            $scope.interfaces = getInterfaces();
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

        // Get the VLAN for the interface.
        $scope.getVLAN = function(nic) {
            return VLANsManager.getItemFromList(nic.vlan_id);
        };

        // Get the fabric for the interface.
        $scope.getFabric = function(nic) {
            var vlan = $scope.getVLAN(nic);
            if(angular.isObject(vlan)) {
                return FabricsManager.getItemFromList(vlan.fabric);
            } else {
                return null;
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
