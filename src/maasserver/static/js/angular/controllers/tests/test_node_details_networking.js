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
    var FabricsManager, VLANsManager, SubnetsManager, NodesManager;
    var ManagerHelperService;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        NodesManager = $injector.get("NodesManager");
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
            NodesManager: NodesManager,
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
        expect($scope.interfaceLinksMap).toEqual({});
        expect($scope.originalInterfaces).toEqual({});
        expect($scope.showingMembers).toEqual([]);
        expect($scope.focusInterface).toBeNull();
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

    describe("updateInterfaces", function() {

        // updateInterfaces is a private method in the controller but we test
        // it by calling nodeLoaded which will setup the watcher which call
        // updateInterfaces and set $scope.interfaces.
        function updateInterfaces() {
            var controller = makeController();
            $scope.nodeLoaded();
            $scope.$digest();
        }

        it("returns empty list when node.interfaces empty", function() {
            node.interfaces = [];
            updateInterfaces();
            expect($scope.interfaces).toEqual([]);
        });

        it("adds interfaces to originalInterfaces map", function() {
            var nic1 = {
                id: 1,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: []
            };
            var nic2 = {
                id: 2,
                name: "eth1",
                type: "physical",
                parents: [],
                children: [],
                links: []
            };
            node.interfaces = [nic1, nic2];
            updateInterfaces();
            expect($scope.originalInterfaces).toEqual({
                1: nic1,
                2: nic2
            });
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
            updateInterfaces();
            expect($scope.interfaces).toEqual([{
                id: 2,
                name: "bond0",
                type: "bond",
                parents: [0, 1],
                children: [],
                links: [],
                members: [parent1, parent2],
                vlan: null,
                link_id: -1,
                subnet_id: null,
                mode: "link_up",
                ip_address: ""
            }]);
        });

        it("clears focusInterface if parent is now in a bond", function() {
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
            $scope.focusInterface = {
                id: 0,
                link_id: -1
            };
            updateInterfaces();
            expect($scope.focusInterface).toBeNull();
        });

        it("sets vlan and fabric on interface", function() {
            var fabric = {
                id: 0
            };
            var vlan = {
                id: 0,
                fabric: 0
            };
            var nic = {
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: [],
                vlan_id: 0
            };
            FabricsManager._items = [fabric];
            VLANsManager._items = [vlan];
            node.interfaces = [nic];
            updateInterfaces();
            expect($scope.interfaces[0].vlan).toBe(vlan);
            expect($scope.interfaces[0].fabric).toBe(fabric);
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
            updateInterfaces();
            expect($scope.interfaces).toEqual([{
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: [],
                vlan: null,
                link_id: -1,
                subnet_id: null,
                mode: "link_up",
                ip_address: ""
            }]);
        });

        it("duplicates links as alias interfaces", function() {
            var links = [
                {
                    id: 0,
                    subnet_id: 0,
                    mode: "dhcp",
                    ip_address: ""
                },
                {
                    id: 1,
                    subnet_id: 1,
                    mode: "auto",
                    ip_address: ""
                },
                {
                    id: 2,
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
            updateInterfaces();
            expect($scope.interfaces).toEqual([
                {
                    id: 0,
                    name: "eth0",
                    type: "physical",
                    parents: [],
                    children: [],
                    links: links,
                    vlan: null,
                    fabric: undefined,
                    link_id: 0,
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
                    vlan: null,
                    fabric: undefined,
                    link_id: 1,
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
                    vlan: null,
                    fabric: undefined,
                    link_id: 2,
                    subnet_id: 2,
                    mode: "static",
                    ip_address: "192.168.122.10"
                }
            ]);
        });

        it("creates interfaceLinksMap", function() {
            var links = [
                {
                    id: 0,
                    subnet_id: 0,
                    mode: "dhcp",
                    ip_address: ""
                },
                {
                    id: 1,
                    subnet_id: 1,
                    mode: "auto",
                    ip_address: ""
                },
                {
                    id: 2,
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
            updateInterfaces();
            expect($scope.interfaceLinksMap[0][0].link_id).toBe(0);
            expect($scope.interfaceLinksMap[0][1].link_id).toBe(1);
            expect($scope.interfaceLinksMap[0][2].link_id).toBe(2);
        });

        it("clears focusInterface if interface no longer exists", function() {
            node.interfaces = [];
            $scope.focusInterface = {
                id: 0,
                link_id: -1
            };
            updateInterfaces();
            expect($scope.focusInterface).toBeNull();
        });

        it("clears focusInterface if link no longer exists", function() {
            var nic = {
                id: 0,
                name: "eth0",
                type: "physical",
                parents: [],
                children: [],
                links: []
            };
            node.interfaces = [nic];
            $scope.focusInterface = {
                id: 0,
                link_id: 0
            };
            updateInterfaces();
            expect($scope.focusInterface).toBeNull();
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

    describe("saveInterface", function() {

        it("does nothing if nothing changed", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var name = makeName("nic");
            var vlan = { id: makeInteger(0, 100) };
            var original_nic = {
                id: id,
                name: name,
                vlan_id: vlan.id
            };
            var nic = {
                id: id,
                name: name,
                vlan: vlan
            };
            $scope.originalInterfaces[id] = original_nic;
            $scope.interfaces = [nic];

            spyOn(NodesManager, "updateInterface").and.returnValue(
                $q.defer().promise);
            $scope.saveInterface(nic);
            expect(NodesManager.updateInterface).not.toHaveBeenCalled();
        });

        it("calls NodesManager.updateInterface if name changed", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var name = makeName("nic");
            var vlan = { id: makeInteger(0, 100) };
            var original_nic = {
                id: id,
                name: name,
                vlan_id: vlan.id
            };
            var nic = {
                id: id,
                name: makeName("newName"),
                vlan: vlan
            };
            $scope.originalInterfaces[id] = original_nic;
            $scope.interfaces = [nic];

            spyOn(NodesManager, "updateInterface").and.returnValue(
                $q.defer().promise);
            $scope.saveInterface(nic);
            expect(NodesManager.updateInterface).toHaveBeenCalledWith(
                node, id, {
                    "name": nic.name,
                    "vlan": vlan.id
                });
        });

        it("calls NodesManager.updateInterface if vlan changed", function() {
            var controller = makeController();
            var id = makeInteger(0, 100);
            var name = makeName("nic");
            var vlan = { id: makeInteger(0, 100) };
            var original_nic = {
                id: id,
                name: name,
                vlan_id: makeInteger(200, 300)
            };
            var nic = {
                id: id,
                name: name,
                vlan: vlan
            };
            $scope.originalInterfaces[id] = original_nic;
            $scope.interfaces = [nic];

            spyOn(NodesManager, "updateInterface").and.returnValue(
                $q.defer().promise);
            $scope.saveInterface(nic);
            expect(NodesManager.updateInterface).toHaveBeenCalledWith(
                node, id, {
                    "name": name,
                    "vlan": vlan.id
                });
        });
    });

    describe("setFocusInterface", function() {

        it("sets focusInterface", function() {
            var controller = makeController();
            var nic = {};
            $scope.setFocusInterface(nic);
            expect($scope.focusInterface).toBe(nic);
        });
    });

    describe("clearFocusInterface", function() {

        it("clears focusInterface no arguments", function() {
            var controller = makeController();
            var nic = {};
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            $scope.clearFocusInterface();
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).toHaveBeenCalledWith(nic);
        });

        it("clears focusInterface if same interface", function() {
            var controller = makeController();
            var nic = {};
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            $scope.clearFocusInterface(nic);
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).toHaveBeenCalledWith(nic);
        });

        it("doesnt clear focusInterface if different interface", function() {
            var controller = makeController();
            var nic = {};
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            $scope.clearFocusInterface({});
            expect($scope.focusInterface).toBe(nic);
            expect($scope.saveInterface).not.toHaveBeenCalled();
        });
    });

    describe("isInterfaceNameInvalid", function() {

        it("returns true if name is empty", function() {
            var controller = makeController();
            var nic = {
                name: ""
            };
            expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
        });

        it("returns true if name is same as another interface", function() {
            var controller = makeController();
            var name = makeName("nic");
            var nic = {
                id: 0,
                name: name
            };
            var otherNic = {
                id: 1,
                name: name
            };
            $scope.node.interfaces = [nic, otherNic];
            expect($scope.isInterfaceNameInvalid(nic)).toBe(true);
        });

        it("returns false if name is same name as self", function() {
            var controller = makeController();
            var name = makeName("nic");
            var nic = {
                id: 0,
                name: name
            };
            $scope.node.interfaces = [nic];
            expect($scope.isInterfaceNameInvalid(nic)).toBe(false);
        });

        it("returns false if name is different", function() {
            var controller = makeController();
            var name = makeName("nic");
            var newName = makeName("newNic");
            var nic = {
                id: 0,
                name: newName
            };
            var otherNic = {
                id: 1,
                name: name
            };
            $scope.node.interfaces = [otherNic];
            expect($scope.isInterfaceNameInvalid(nic)).toBe(false);
        });
    });

    describe("fabricChanged", function() {

        it("sets vlan on interface", function() {
            var controller = makeController();
            var fabric = {
                id: 0,
                vlan_ids: [0]
            };
            var vlan = {
                id: 0,
                fabric: fabric.id
            };
            FabricsManager._items = [fabric];
            VLANsManager._items = [vlan];
            var nic = {
                vlan: null,
                fabric: fabric
            };
            spyOn($scope, "saveInterface");
            $scope.fabricChanged(nic);
            expect(nic.vlan).toBe(vlan);
        });

        it("calls saveInterface", function() {
            var controller = makeController();
            var fabric = {
                id: 0,
                vlan_ids: [0]
            };
            var vlan = {
                id: 0,
                fabric: fabric.id
            };
            FabricsManager._items = [fabric];
            VLANsManager._items = [vlan];
            var nic = {
                vlan: null,
                fabric: fabric
            };
            spyOn($scope, "saveInterface");
            $scope.fabricChanged(nic);
            expect($scope.saveInterface).toHaveBeenCalledWith(nic);
        });
    });
});
