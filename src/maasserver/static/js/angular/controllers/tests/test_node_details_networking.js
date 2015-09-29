/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeNetworkingController.
 */

describe("NodeNetworkingController", function() {
    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $parentScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $parentScope = $rootScope.$new();
        $scope = $parentScope.$new();
        $q = $injector.get("$q");
    }));

    // Load the required dependencies for the NodeNetworkingController.
    var FabricsManager, VLANsManager, SubnetsManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Create the node on the parent.
    var node;
    beforeEach(function() {
        node = {
            interfaces: []
        };
        $parentScope.node = node;
    });

    // Makes the NodeStorageController.
    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("NodeNetworkingController", {
            $scope: $scope,
            FabricsManager: FabricsManager,
            VLANsManager: VLANsManager,
            SubnetsManager: SubnetsManager,
            ManagerHelperService: ManagerHelperService
        });
        return controller;
    }

    it("sets initial values", function() {
        var controller = makeController();
        expect($scope.loaded).toBe(false);
        expect($scope.nodeHasLoaded).toBe(false);
        expect($scope.managersHaveLoaded).toBe(false);
        expect($scope.column).toBe('name');
        expect($scope.interfaces).toEqual([]);
        expect($scope.showingMembers).toEqual([]);
    });

    it("sets loaded once node loaded then managers loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);

        // All should false.
        expect($scope.loaded).toBe(false);
        expect($scope.nodeHasLoaded).toBe(false);
        expect($scope.managersHaveLoaded).toBe(false);

        // Only nodeHasLoaded should be true.
        $scope.nodeLoaded();
        expect($scope.loaded).toBe(false);
        expect($scope.nodeHasLoaded).toBe(true);
        expect($scope.managersHaveLoaded).toBe(false);

        // All three should be true.
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loaded).toBe(true);
        expect($scope.nodeHasLoaded).toBe(true);
        expect($scope.managersHaveLoaded).toBe(true);
    });

    it("sets loaded once managers loaded then node loaded", function() {
        var defer = $q.defer();
        var controller = makeController(defer);

        // All should false.
        expect($scope.loaded).toBe(false);
        expect($scope.nodeHasLoaded).toBe(false);
        expect($scope.managersHaveLoaded).toBe(false);

        // Only managersHaveLoaded should be true.
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loaded).toBe(false);
        expect($scope.nodeHasLoaded).toBe(false);
        expect($scope.managersHaveLoaded).toBe(true);

        // All three should be true.
        $scope.nodeLoaded();
        expect($scope.loaded).toBe(true);
        expect($scope.nodeHasLoaded).toBe(true);
        expect($scope.managersHaveLoaded).toBe(true);
    });

    it("starts watching interfaces once nodeLoaded called", function() {
        var controller = makeController();

        spyOn($scope, "$watch");
        $scope.nodeLoaded();

        var watches = [];
        var i, calls = $scope.$watch.calls.allArgs();
        for(i = 0; i < calls.length; i++) {
            watches.push(calls[i][0]);
        }

        expect(watches).toEqual(["node.interfaces"]);
    });

    describe("getInterfaces", function() {

        // getInterfaces is a private method in the controller but we test it
        // by calling nodeLoaded which will setup the watcher which will set
        // $scope.interfaces variable with the output from getInterfaces.
        function getInterfaces() {
            var controller = makeController();
            $scope.nodeLoaded();
            $scope.$digest();
            return $scope.interfaces;
        }

        it("returns empty list when node.interfaces empty", function() {
            node.interfaces = [];
            expect(getInterfaces()).toEqual([]);
        });

        it("removes bond parents and places them as members", function() {
            var parent1 = {
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [2],
                links: []
            };
            var parent2 = {
                id: 1,
                name: "eth1",
                type: "physical",
                parents: [],
                children: [2],
                links: []
            };
            var bond = {
                id: 2,
                name: "bond0",
                type: "bond",
                parents: [0, 1],
                children: [],
                links: []
            };
            node.interfaces = [parent1, parent2, bond];
            expect(getInterfaces()).toEqual([{
                id: 2,
                name: "bond0",
                type: "bond",
                parents: [0, 1],
                children: [],
                links: [],
                members: [parent1, parent2],
                subnet_id: null,
                mode: "link_up",
                ip_address: ""
            }]);
        });

        it("sets default to link_up if not links", function() {
            var nic = {
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: []
            };
            node.interfaces = [nic];
            expect(getInterfaces()).toEqual([{
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: [],
                subnet_id: null,
                mode: "link_up",
                ip_address: ""
            }]);
        });

        it("duplicates links as alias interfaces", function() {
            var links = [
                {
                    subnet_id: 0,
                    mode: "dhcp",
                    ip_address: ""
                },
                {
                    subnet_id: 1,
                    mode: "auto",
                    ip_address: ""
                },
                {
                    subnet_id: 2,
                    mode: "static",
                    ip_address: "192.168.122.10"
                }
            ];
            var nic = {
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: links
            };
            node.interfaces = [nic];
            expect(getInterfaces()).toEqual([
                {
                    id: 0,
                    name: "eth0",
                    type: "physical",
                    parents: [],
                    children: [],
                    links: links,
                    subnet_id: 0,
                    mode: "dhcp",
                    ip_address: ""
                },
                {
                    id: 0,
                    name: "eth0:1",
                    type: "alias",
                    parents: [],
                    children: [],
                    links: links,
                    subnet_id: 1,
                    mode: "auto",
                    ip_address: ""
                },
                {
                    id: 0,
                    name: "eth0:2",
                    type: "alias",
                    parents: [],
                    children: [],
                    links: links,
                    subnet_id: 2,
                    mode: "static",
                    ip_address: "192.168.122.10"
                }
            ]);
        });
    });

    describe("getInterfaceTypeText", function() {
        var INTERFACE_TYPE_TEXTS = {
            "physical": "Physical",
            "bond": "Bond",
            "vlan": "VLAN",
            "alias": "Alias",
            "missing_type": "missing_type"
        };

        angular.forEach(INTERFACE_TYPE_TEXTS, function(value, type) {
            it("returns correct value for '" + type + "'", function() {
                var controller = makeController();
                var nic = {
                    type: type
                };
                expect($scope.getInterfaceTypeText(nic)).toBe(value);
            });
        });
    });

    describe("getLinkModeText", function() {
        var LINK_MODE_TEXTS = {
            "auto": "Auto assign",
            "static": "Static assign",
            "dhcp": "DHCP",
            "link_up": "Unconfigured",
            "missing_type": "missing_type"
        };

        angular.forEach(LINK_MODE_TEXTS, function(value, mode) {
            it("returns correct value for '" + mode + "'", function() {
                var controller = makeController();
                var nic = {
                    mode: mode
                };
                expect($scope.getLinkModeText(nic)).toBe(value);
            });
        });
    });

    describe("getVLAN", function() {

        it("returns item from VLANsManager", function() {
            var controller = makeController();
            var vlan_id = makeInteger(0, 100);
            var vlan = {
                id: vlan_id
            };
            VLANsManager._items = [vlan];

            var nic = {
                vlan_id: vlan_id
            };
            expect($scope.getVLAN(nic)).toBe(vlan);
        });

        it("returns null for missing VLAN", function() {
            var controller = makeController();
            var vlan_id = makeInteger(0, 100);
            var nic = {
                vlan_id: vlan_id
            };
            expect($scope.getVLAN(nic)).toBeNull();
        });
    });

    describe("getFabric", function() {

        it("returns item from FabricsManager", function() {
            var controller = makeController();
            var fabric_id = makeInteger(0, 100);
            var fabric = {
                id: fabric_id
            };
            FabricsManager._items = [fabric];

            var vlan_id = makeInteger(0, 100);
            var vlan = {
                id: vlan_id,
                fabric: fabric_id
            };
            VLANsManager._items = [vlan];

            var nic = {
                vlan_id: vlan_id
            };
            expect($scope.getFabric(nic)).toBe(fabric);
        });

        it("returns null for missing VLAN", function() {
            var controller = makeController();
            var vlan_id = makeInteger(0, 100);
            var nic = {
                vlan_id: vlan_id
            };
            expect($scope.getFabric(nic)).toBeNull();
        });

        it("returns null for missing fabric", function() {
            var controller = makeController();
            var fabric_id = makeInteger(0, 100);
            var vlan_id = makeInteger(0, 100);
            var vlan = {
                id: vlan_id,
                fabric: fabric_id
            };
            VLANsManager._items = [vlan];

            var nic = {
                vlan_id: vlan_id
            };
            expect($scope.getFabric(nic)).toBeNull();
        });
    });

    describe("getSubnet", function() {

        it("returns item from SubnetsManager", function() {
            var controller = makeController();
            var subnet_id = makeInteger(0, 100);
            var subnet = {
                id: subnet_id
            };
            SubnetsManager._items = [subnet];

            var nic = {
                subnet_id: subnet_id
            };
            expect($scope.getSubnet(nic)).toBe(subnet);
        });

        it("returns null for missing subnet", function() {
            var controller = makeController();
            var subnet_id = makeInteger(0, 100);
            var nic = {
                subnet_id: subnet_id
            };
            expect($scope.getSubnet(nic)).toBeNull();
        });
    });

    describe("getSubnetName", function() {

        it("returns name from item in SubnetsManager", function() {
            var controller = makeController();
            var subnet_id = makeInteger(0, 100);
            var subnet_name = makeName("subnet");
            var subnet = {
                id: subnet_id,
                name: subnet_name
            };
            SubnetsManager._items = [subnet];

            var nic = {
                subnet_id: subnet_id
            };
            expect($scope.getSubnetName(nic)).toBe(subnet_name);
        });

        it("returns 'Unknown' if item not in SubnetsManager", function() {
            var controller = makeController();
            var nic = {
                subnet_id: makeInteger(0, 100)
            };
            expect($scope.getSubnetName(nic)).toBe("Unknown");
        });

        it("returns 'Unconfigured' if no subnet_id", function() {
            var controller = makeController();
            var nic = {
                subnet_id: null
            };
            expect($scope.getSubnetName(nic)).toBe("Unconfigured");
        });
    });

    describe("toggleMembers", function() {

        it("adds interface id to showingMembers", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100)
            };
            $scope.toggleMembers(nic);
            expect($scope.showingMembers).toEqual([nic.id]);
        });

        it("removes interface id from showingMembers", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100)
            };
            $scope.showingMembers = [nic.id];
            $scope.toggleMembers(nic);
            expect($scope.showingMembers).toEqual([]);
        });
    });

    describe("isShowingMembers", function() {

        it("returns true if interface id in showingMembers", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100)
            };
            $scope.showingMembers = [nic.id];
            expect($scope.isShowingMembers(nic)).toBe(true);
        });

        it("returns true if interface id in showingMembers", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100)
            };
            $scope.showingMembers = [];
            expect($scope.isShowingMembers(nic)).toBe(false);
        });
    });
});
