/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeNetworkingController.
 */

describe("filterByUnusedForInterface", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the filterByUnusedForInterface.
    var filterByUnusedForInterface;
    beforeEach(inject(function($filter) {
        filterByUnusedForInterface = $filter("filterByUnusedForInterface");
    }));

    it("returns empty if undefined nic", function() {
        var i, vlan, vlans = [];
        for(i = 0; i < 3; i++) {
            vlan = {
                fabric: 0
            };
            vlans.push(vlan);
        }
        expect(filterByUnusedForInterface(vlans)).toEqual([]);
    });

    it("returns only free vlans", function() {
        var i, vlan, used_vlans = [], free_vlans = [], all_vlans = [];
        for(i = 0; i < 3; i++) {
            vlan = {
                id: i,
                fabric: 0
            };
            used_vlans.push(vlan);
            all_vlans.push(vlan);
        }
        for(i = 3; i < 6; i++) {
            vlan = {
                id: i,
                fabric: 0
            };
            free_vlans.push(vlan);
            all_vlans.push(vlan);
        }

        var nic = {
            id: 0
        };
        var originalInterfaces = {
            0: {
                type: "vlan",
                parents: [0],
                vlan_id: used_vlans[0].id
            },
            1: {
                type: "vlan",
                parents: [0],
                vlan_id: used_vlans[1].id
            },
            2: {
                type: "vlan",
                parents: [0],
                vlan_id: used_vlans[2].id
            },
            3: {
                type: "physical",
                vlan_id: free_vlans[0].id
            }
        };

        expect(
            filterByUnusedForInterface(
                all_vlans, nic, originalInterfaces)).toEqual(free_vlans);
    });
});


describe("removeBondParents", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the removeBondParents.
    var removeBondParents;
    beforeEach(inject(function($filter) {
        removeBondParents = $filter("removeBondParents");
    }));

    it("returns empty if undefined bondInterface", function() {
        var i, nic, interfaces = [];
        for(i = 0; i < 3; i++) {
            nic = {
                id: i,
                link_id: i
            };
            interfaces.push(nic);
        }
        expect(removeBondParents(interfaces)).toEqual(interfaces);
    });

    it("removes parents from interfaces", function() {
        var vlan = {
            id: makeInteger(0, 100)
        };
        var nic1 = {
            id: makeInteger(0, 100),
            link_id: makeInteger(0, 100),
            type: "physical",
            vlan: vlan
        };
        var nic2 = {
            id: makeInteger(0, 100),
            link_id: makeInteger(0, 100),
            type: "physical",
            vlan: vlan
        };
        var interfaces = [nic1, nic2];
        var bondInterface = {
            parents: interfaces
        };
        expect(removeBondParents(interfaces, bondInterface)).toEqual([]);
    });
});


describe("removeDefaultVLANIfVLAN", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the removeDefaultVLANIfVLAN.
    var removeDefaultVLANIfVLAN;
    beforeEach(inject(function($filter) {
        removeDefaultVLANIfVLAN = $filter("removeDefaultVLANIfVLAN");
    }));

    it("returns vlans if undefined type", function() {
        var i, vlan, vlans = [];
        for(i = 0; i < 3; i++) {
            vlan = {
                id: i,
                vid: i,
                fabric: 0
            };
            vlans.push(vlan);
        }
        expect(removeDefaultVLANIfVLAN(vlans)).toEqual(vlans);
    });

    it("removes default vlans from vlans", function() {
        var i, vlan, vlans = [];
        for(i = 0; i < 3; i++) {
            vlan = {
                id: i,
                vid: i,
                fabric: 0
            };
            vlans.push(vlan);
        }

        expect(
            removeDefaultVLANIfVLAN(
                vlans, "vlan")).toEqual([vlans[1], vlans[2]]);
    });
});


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
    var GeneralManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        NodesManager = $injector.get("NodesManager");
        GeneralManager = $injector.get("GeneralManager");
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
            GeneralManager: GeneralManager,
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
        expect($scope.fabrics).toBe(FabricsManager.getItems());
        expect($scope.vlans).toBe(VLANsManager.getItems());
        expect($scope.subnets).toBe(SubnetsManager.getItems());
        expect($scope.interfaces).toEqual([]);
        expect($scope.interfaceLinksMap).toEqual({});
        expect($scope.originalInterfaces).toEqual({});
        expect($scope.showingMembers).toEqual([]);
        expect($scope.focusInterface).toBeNull();
        expect($scope.selectedInterfaces).toEqual([]);
        expect($scope.selectedMode).toBeNull();
        expect($scope.newInterface).toEqual({});
        expect($scope.newBondInterface).toEqual({});
        expect($scope.bondOptions).toBe(
            GeneralManager.getData("bond_options"));
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
        function updateInterfaces(controller) {
            if(!angular.isObject(controller)) {
                controller = makeController();
            }
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
                subnet: null,
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
                subnet: null,
                mode: "link_up",
                ip_address: ""
            }]);
        });

        it("duplicates links as alias interfaces", function() {
            var subnet0 = { id: 0 }, subnet1 = { id: 1 }, subnet2 = { id: 2 };
            SubnetsManager._items = [subnet0, subnet1, subnet2];
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
                    subnet: subnet0,
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
                    subnet: subnet1,
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
                    subnet: subnet2,
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

        describe("newInterface", function() {

            // Setup the initial data for newInterface to be set.
            function setupNewInterface(controller, newInterface) {
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
                updateInterfaces(controller);

                var parent = $scope.interfaceLinksMap[0][0];
                newInterface.parent = parent;
                $scope.newInterface = newInterface;
            }

            // Cause the updateInterfaces to be called again to perform
            // the logic on newInterface.
            function reloadNewInterface(controller) {
                // Add another nic to interfaces so that updateInterfaces
                // really performs an action.
                node.interfaces.push({
                    id: 1,
                    name: "eth1",
                    type: "physical",
                    parents: [],
                    children: [],
                    links: []
                });
                updateInterfaces(controller);
            }

            it("updates newInterface.parent object", function() {
                var controller = makeController();
                var newInterface = {
                    type: "vlan"
                };
                setupNewInterface(controller, newInterface);
                var parent = newInterface.parent;
                reloadNewInterface(controller);

                // Should be the same value but a different object.
                expect(newInterface.parent).toEqual(parent);
                expect(newInterface.parent).not.toBe(parent);
            });

            it("changes newInterface.type from alias to VLAN", function() {
                var controller = makeController();
                var newInterface = {
                    type: "alias"
                };
                setupNewInterface(controller, newInterface);

                spyOn($scope, "canAddAlias").and.returnValue(false);
                spyOn($scope, "canAddVLAN").and.returnValue(true);
                spyOn($scope, "addTypeChanged");
                reloadNewInterface(controller);
                expect(newInterface.type).toBe("vlan");
                expect($scope.addTypeChanged).toHaveBeenCalled();
            });

            it("changes newInterface.type from VLAN to alias", function() {
                var controller = makeController();
                var newInterface = {
                    type: "vlan"
                };
                setupNewInterface(controller, newInterface);

                spyOn($scope, "canAddAlias").and.returnValue(true);
                spyOn($scope, "canAddVLAN").and.returnValue(false);
                spyOn($scope, "addTypeChanged");
                reloadNewInterface(controller);
                expect(newInterface.type).toBe("alias");
                expect($scope.addTypeChanged).toHaveBeenCalled();
            });

            it("clears newInterface if cannot add VLAN or alias", function() {
                var controller = makeController();
                var newInterface = {
                    type: "vlan"
                };
                setupNewInterface(controller, newInterface);

                spyOn($scope, "canAddAlias").and.returnValue(false);
                spyOn($scope, "canAddVLAN").and.returnValue(false);
                reloadNewInterface(controller);
                expect($scope.newInterface).toEqual({});
            });

            it("clears newInterface if parent removed",
                function() {
                    var controller = makeController();
                    var newInterface = {
                        type: "vlan"
                    };
                    setupNewInterface(controller, newInterface);

                    spyOn($scope, "canAddAlias").and.returnValue(false);
                    spyOn($scope, "canAddVLAN").and.returnValue(false);
                    $scope.selectedMode = "add";
                    reloadNewInterface(controller);
                    expect($scope.selectedMode).toBeNull();
                });

            it("leaves single selection mode if newInterface is cleared",
                function() {
                    var controller = makeController();
                    var newInterface = {
                        type: "vlan"
                    };
                    setupNewInterface(controller, newInterface);

                    spyOn($scope, "canAddAlias").and.returnValue(false);
                    spyOn($scope, "canAddVLAN").and.returnValue(false);
                    $scope.selectedMode = "add";
                    node.interfaces = [];
                    updateInterfaces(controller);
                    expect($scope.newInterface).toEqual({});
                    expect($scope.selectedMode).toBeNull();
                });
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

    describe("getVLANText", function() {

        it("returns empty if vlan undefined", function() {
            var controller = makeController();
            expect($scope.getVLANText()).toBe("");
        });

        it("returns just vid", function() {
            var controller = makeController();
            var vlan = {
                vid: 5
            };
            expect($scope.getVLANText(vlan)).toBe(5);
        });

        it("returns vid + name", function() {
            var controller = makeController();
            var name = makeName("vlan");
            var vlan = {
                vid: 5,
                name: name
            };
            expect($scope.getVLANText(vlan)).toBe("5 (" + name + ")");
        });
    });

    describe("getSubnetText", function() {

        it("returns 'Unconfigured' for null", function() {
            var controller = makeController();
            expect($scope.getSubnetText(null)).toBe("Unconfigured");
        });

        it("returns just cidr if no name", function() {
            var controller = makeController();
            var cidr = makeName("cidr");
            var subnet = {
                cidr: cidr
            };
            expect($scope.getSubnetText(subnet)).toBe(cidr);
        });

        it("returns just cidr if name same as cidr", function() {
            var controller = makeController();
            var cidr = makeName("cidr");
            var subnet = {
                cidr: cidr,
                name: cidr
            };
            expect($scope.getSubnetText(subnet)).toBe(cidr);
        });

        it("returns cidr + name", function() {
            var controller = makeController();
            var cidr = makeName("cidr");
            var name = makeName("name");
            var subnet = {
                cidr: cidr,
                name: name
            };
            expect($scope.getSubnetText(subnet)).toBe(
                cidr + " (" + name + ")");
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

        it("resets name if its invalid and doesn't call update", function() {
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
                name: "",
                vlan: vlan
            };
            $scope.originalInterfaces[id] = original_nic;
            $scope.interfaces = [nic];

            spyOn(NodesManager, "updateInterface").and.returnValue(
                $q.defer().promise);
            $scope.saveInterface(nic);
            expect(nic.name).toBe(name);
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
            var nic = {
                type: "physical"
            };
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            spyOn($scope, "saveInterfaceIPAddress");
            $scope.clearFocusInterface();
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).toHaveBeenCalledWith(nic);
            expect($scope.saveInterfaceIPAddress).toHaveBeenCalledWith(nic);
        });

        it("clears focusInterface if same interface", function() {
            var controller = makeController();
            var nic = {
                type: "physical"
            };
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            spyOn($scope, "saveInterfaceIPAddress");
            $scope.clearFocusInterface(nic);
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).toHaveBeenCalledWith(nic);
            expect($scope.saveInterfaceIPAddress).toHaveBeenCalledWith(nic);
        });

        it("doesnt clear focusInterface if different interface", function() {
            var controller = makeController();
            var nic = {
                type: "physical"
            };
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            spyOn($scope, "saveInterfaceIPAddress");
            $scope.clearFocusInterface({});
            expect($scope.focusInterface).toBe(nic);
            expect($scope.saveInterface).not.toHaveBeenCalled();
            expect($scope.saveInterfaceIPAddress).not.toHaveBeenCalled();
        });

        it("doesnt call save with focusInterface no arguments", function() {
            var controller = makeController();
            var nic = {
                type: "alias"
            };
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            spyOn($scope, "saveInterfaceIPAddress");
            $scope.clearFocusInterface();
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).not.toHaveBeenCalled();
            expect($scope.saveInterfaceIPAddress).toHaveBeenCalledWith(nic);
        });

        it("doesnt call save with focusInterface if same nic", function() {
            var controller = makeController();
            var nic = {
                type: "alias"
            };
            $scope.focusInterface = nic;
            spyOn($scope, "saveInterface");
            spyOn($scope, "saveInterfaceIPAddress");
            $scope.clearFocusInterface(nic);
            expect($scope.focusInterface).toBeNull();
            expect($scope.saveInterface).not.toHaveBeenCalled();
            expect($scope.saveInterfaceIPAddress).toHaveBeenCalledWith(nic);
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

    describe("isLinkModeDisabled", function() {

        it("enabled when subnet", function() {
            var controller = makeController();
            var nic = {
                subnet : {}
            };
            expect($scope.isLinkModeDisabled(nic)).toBe(false);
        });

        it("disabled when not subnet", function() {
            var controller = makeController();
            var nic = {
                subnet : null
            };
            expect($scope.isLinkModeDisabled(nic)).toBe(true);
        });
    });

    describe("getLinkModes", function() {

        it("only link_up when no subnet", function() {
            var controller = makeController();
            var nic = {
                subnet : null
            };
            expect($scope.getLinkModes(nic)).toEqual([
                {
                    "mode": "link_up",
                    "text": "Unconfigured"
                }
            ]);
        });

        it("all modes if only one link", function() {
            var controller = makeController();
            var nic = {
                subnet : {},
                links: [{}]
            };
            expect($scope.getLinkModes(nic)).toEqual([
                {
                    "mode": "auto",
                    "text": "Auto assign"
                },
                {
                    "mode": "static",
                    "text": "Static assign"
                },
                {
                    "mode": "dhcp",
                    "text": "DHCP"
                },
                {
                    "mode": "link_up",
                    "text": "Unconfigured"
                }
            ]);
        });

        it("auto and static modes if more than one link", function() {
            var controller = makeController();
            var nic = {
                subnet : {},
                links: [{}, {}]
            };
            expect($scope.getLinkModes(nic)).toEqual([
                {
                    "mode": "auto",
                    "text": "Auto assign"
                },
                {
                    "mode": "static",
                    "text": "Static assign"
                }
            ]);
        });

        it("auto and static modes if interface is alias", function() {
            var controller = makeController();
            var nic = {
                type: "alias",
                subnet : {}
            };
            expect($scope.getLinkModes(nic)).toEqual([
                {
                    "mode": "auto",
                    "text": "Auto assign"
                },
                {
                    "mode": "static",
                    "text": "Static assign"
                }
            ]);
        });
    });

    describe("saveInterfaceLink", function() {

        it("calls NodesManager.linkSubnet with params", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                mode: "static",
                subnet: { id: makeInteger(0, 100) },
                link_id: makeInteger(0, 100),
                ip_address: "192.168.122.1"
            };
            spyOn(NodesManager, "linkSubnet").and.returnValue(
                $q.defer().promise);
            $scope.saveInterfaceLink(nic);
            expect(NodesManager.linkSubnet).toHaveBeenCalledWith(
                node, nic.id, {
                    "mode": "static",
                    "subnet": nic.subnet.id,
                    "link_id": nic.link_id,
                    "ip_address": nic.ip_address
                });
        });
    });

    describe("subnetChanged", function() {

        it("sets mode to link_up if set to no subnet", function() {
            var controller = makeController();
            var nic = {
                subnet: null
            };
            spyOn($scope, "saveInterfaceLink");
            $scope.subnetChanged(nic);
            expect(nic.mode).toBe("link_up");
            expect($scope.saveInterfaceLink).toHaveBeenCalledWith(nic);
        });

        it("doesnt set mode to link_up if set if subnet", function() {
            var controller = makeController();
            var nic = {
                mode: "static",
                subnet: {}
            };
            spyOn($scope, "saveInterfaceLink");
            $scope.subnetChanged(nic);
            expect(nic.mode).toBe("static");
            expect($scope.saveInterfaceLink).toHaveBeenCalledWith(nic);
        });

        it("clears ip_address", function() {
            var controller = makeController();
            var nic = {
                subnet: null,
                ip_address: makeName("ip")
            };
            spyOn($scope, "saveInterfaceLink");
            $scope.subnetChanged(nic);
            expect(nic.ip_address).toBe("");
        });
    });

    describe("shouldShowIPAddress", function() {

        it("true if not static and has ip address", function() {
            var controller = makeController();
            var nic = {
                mode: "auto",
                ip_address: "192.168.122.1"
            };
            expect($scope.shouldShowIPAddress(nic)).toBe(true);
        });

        it("false if not static and doesn't have ip address", function() {
            var controller = makeController();
            var nic = {
                mode: "dhcp",
                ip_address: ""
            };
            expect($scope.shouldShowIPAddress(nic)).toBe(false);
        });

        describe("static", function() {

            it("false if no orginial link", function() {
                var controller = makeController();
                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: -1,
                    ip_address: ""
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(false);
            });

            it("false if orginial link has no IP address", function() {
                var controller = makeController();
                var originalInterface = {
                    id: 0,
                    links: [
                        {
                            id: 0,
                            mode: "static"
                        }
                    ]
                };
                $scope.originalInterfaces = [originalInterface];

                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: 0,
                    ip_address: ""
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(false);
            });

            it("false if orginial link has empty IP address", function() {
                var controller = makeController();
                var originalInterface = {
                    id: 0,
                    links: [
                        {
                            id: 0,
                            mode: "static",
                            ip_address: ""
                        }
                    ]
                };
                $scope.originalInterfaces = [originalInterface];

                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: 0,
                    ip_address: ""
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(false);
            });

            it("false if no subnet on nic", function() {
                var controller = makeController();
                var originalInterface = {
                    id: 0,
                    links: [
                        {
                            id: 0,
                            mode: "static",
                            ip_address: "192.168.122.2"
                        }
                    ]
                };
                $scope.originalInterfaces = [originalInterface];

                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: 0,
                    ip_address: ""
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(false);
            });

            it("false if the subnets don't match", function() {
                var controller = makeController();
                var originalInterface = {
                    id: 0,
                    links: [
                        {
                            id: 0,
                            mode: "static",
                            ip_address: "192.168.122.2",
                            subnet_id: 0
                        }
                    ]
                };
                $scope.originalInterfaces = [originalInterface];

                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: 0,
                    ip_address: "",
                    subnet: {
                        id: 1
                    }
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(false);
            });

            it("true if all condititions match", function() {
                var controller = makeController();
                var originalInterface = {
                    id: 0,
                    links: [
                        {
                            id: 0,
                            mode: "static",
                            ip_address: "192.168.122.2",
                            subnet_id: 0
                        }
                    ]
                };
                $scope.originalInterfaces = [originalInterface];

                var nic = {
                    id: 0,
                    mode: "static",
                    link_id: 0,
                    ip_address: "",
                    subnet: {
                        id: 0
                    }
                };
                expect($scope.shouldShowIPAddress(nic)).toBe(true);
            });
        });
    });

    describe("isIPAddressInvalid", function() {

        it("true if empty IP address", function() {
            var controller = makeController();
            var nic = {
                ip_address: ""
            };
            expect($scope.isIPAddressInvalid(nic)).toBe(true);
        });

        it("true if not valid IP address", function() {
            var controller = makeController();
            var nic = {
                ip_address: "192.168.260.5"
            };
            expect($scope.isIPAddressInvalid(nic)).toBe(true);
        });

        it("true if IP address not in subnet", function() {
            var controller = makeController();
            var nic = {
                ip_address: "192.168.123.10",
                subnet: {
                    cidr: "192.168.122.0/24"
                }
            };
            expect($scope.isIPAddressInvalid(nic)).toBe(true);
        });

        it("false if IP address in subnet", function() {
            var controller = makeController();
            var nic = {
                ip_address: "192.168.122.10",
                subnet: {
                    cidr: "192.168.122.0/24"
                }
            };
            expect($scope.isIPAddressInvalid(nic)).toBe(false);
        });
    });

    describe("saveInterfaceIPAddress", function() {

        it("resets IP address if invalid doesn't save", function() {
            var controller = makeController();
            var originalInterface = {
                id: 0,
                links: [
                    {
                        id: 0,
                        mode: "static",
                        ip_address: "192.168.122.10",
                        subnet_id: 0
                    }
                ]
            };
            $scope.originalInterfaces = [originalInterface];

            var nic = {
                id: 0,
                mode: "static",
                link_id: 0,
                ip_address: "192.168.123.10",
                subnet: {
                    id: 0,
                    cidr: "192.168.122.0/24"
                }
            };
            spyOn($scope, "saveInterfaceLink");
            $scope.saveInterfaceIPAddress(nic);
            expect(nic.ip_address).toBe("192.168.122.10");
            expect($scope.saveInterfaceLink).not.toHaveBeenCalled();
        });

        it("saves the link if valid", function() {
            var controller = makeController();
            var originalInterface = {
                id: 0,
                links: [
                    {
                        id: 0,
                        mode: "static",
                        ip_address: "192.168.122.10",
                        subnet_id: 0
                    }
                ]
            };
            $scope.originalInterfaces = [originalInterface];

            var nic = {
                id: 0,
                mode: "static",
                link_id: 0,
                ip_address: "192.168.122.11",
                subnet: {
                    id: 0,
                    cidr: "192.168.122.0/24"
                }
            };
            spyOn($scope, "saveInterfaceLink");
            $scope.saveInterfaceIPAddress(nic);
            expect(nic.ip_address).toBe("192.168.122.11");
            expect($scope.saveInterfaceLink).toHaveBeenCalledWith(nic);
        });
    });

    describe("getUniqueKey", function() {

        it("returns id + / + link_id", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            expect($scope.getUniqueKey(nic)).toBe(nic.id + "/" + nic.link_id);
        });
    });

    describe("toggleInterfaceSelect", function() {

        it("selects interface and enters single mode", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var key = $scope.getUniqueKey(nic);
            $scope.toggleInterfaceSelect(nic);
            expect($scope.selectedInterfaces).toEqual([key]);
            expect($scope.selectedMode).toBe("single");
        });

        it("deselects interface and enters none mode", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var key = $scope.getUniqueKey(nic);
            $scope.toggleInterfaceSelect(nic);
            $scope.toggleInterfaceSelect(nic);
            expect($scope.selectedInterfaces).toEqual([]);
            expect($scope.selectedMode).toBeNull();
        });

        it("selecting multiple enters multi mode", function() {
            var controller = makeController();
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var nic2 = {
                id: makeInteger(100, 200),
                link_id: makeInteger(0, 100)
            };
            var key1 = $scope.getUniqueKey(nic1);
            var key2 = $scope.getUniqueKey(nic2);
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            expect($scope.selectedInterfaces).toEqual([key1, key2]);
            expect($scope.selectedMode).toBe("multi");
        });
    });

    describe("isInterfaceSelected", function() {

        it("returns true when selected", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var key = $scope.getUniqueKey(nic);
            $scope.selectedInterfaces = [key];
            expect($scope.isInterfaceSelected(nic)).toBe(true);
        });

        it("returns false when not selected", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            $scope.selectedInterfaces = [];
            expect($scope.isInterfaceSelected(nic)).toBe(false);
        });
    });

    describe("isOnlyInterfaceSelected", function() {

        it("returns true when only one selected", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var key = $scope.getUniqueKey(nic);
            $scope.selectedInterfaces = [key];
            expect($scope.isOnlyInterfaceSelected(nic)).toBe(true);
        });

        it("returns false when multiple selected", function() {
            var controller = makeController();
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            var nic2 = {
                id: makeInteger(100, 200),
                link_id: makeInteger(0, 100)
            };
            var key1 = $scope.getUniqueKey(nic1);
            var key2 = $scope.getUniqueKey(nic2);
            $scope.selectedInterfaces = [key1, key2];
            expect($scope.isOnlyInterfaceSelected(nic1)).toBe(false);
        });

        it("returns false when not selected", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            $scope.selectedInterfaces = [];
            expect($scope.isOnlyInterfaceSelected(nic)).toBe(false);
        });
    });

    describe("isShowingInterfaceOptions", function() {

        it("returns true in single mode", function() {
            var controller = makeController();
            $scope.selectedMode = "single";
            expect($scope.isShowingInterfaceOptions()).toBe(true);
        });

        it("returns false not in single mode", function() {
            var controller = makeController();
            $scope.selectedMode = "mutli";
            expect($scope.isShowingInterfaceOptions()).toBe(false);
        });
    });

    describe("isShowingDeleteComfirm", function() {

        it("returns true in delete mode", function() {
            var controller = makeController();
            $scope.selectedMode = "delete";
            expect($scope.isShowingDeleteComfirm()).toBe(true);
        });

        it("returns false not in delete mode", function() {
            var controller = makeController();
            $scope.selectedMode = "single";
            expect($scope.isShowingDeleteComfirm()).toBe(false);
        });
    });

    describe("isShowingAdd", function() {

        it("returns true in add mode", function() {
            var controller = makeController();
            $scope.selectedMode = "add";
            expect($scope.isShowingAdd()).toBe(true);
        });

        it("returns false not in add mode", function() {
            var controller = makeController();
            $scope.selectedMode = "delete";
            expect($scope.isShowingAdd()).toBe(false);
        });
    });

    describe("canAddAlias", function() {

        it("returns false if nic undefined", function() {
            var controller = makeController();
            expect($scope.canAddAlias()).toBe(false);
        });

        it("returns false if nic type is alias", function() {
            var controller = makeController();
            var nic = {
                type: "alias"
            };
            expect($scope.canAddAlias(nic)).toBe(false);
        });

        it("returns false if nic has no links", function() {
            var controller = makeController();
            var nic = {
                type: "physical",
                links: []
            };
            expect($scope.canAddAlias(nic)).toBe(false);
        });

        it("returns false if nic has link_up", function() {
            var controller = makeController();
            var nic = {
                type: "physical",
                links: [{
                    mode: "link_up"
                }]
            };
            expect($scope.canAddAlias(nic)).toBe(false);
        });

        it("returns false if nic has dhcp", function() {
            var controller = makeController();
            var nic = {
                type: "physical",
                links: [{
                    mode: "dhcp"
                }]
            };
            expect($scope.canAddAlias(nic)).toBe(false);
        });

        it("returns true if nic has static", function() {
            var controller = makeController();
            var nic = {
                type: "physical",
                links: [{
                    mode: "static"
                }]
            };
            expect($scope.canAddAlias(nic)).toBe(true);
        });

        it("returns true if nic has auto", function() {
            var controller = makeController();
            var nic = {
                type: "physical",
                links: [{
                    mode: "auto"
                }]
            };
            expect($scope.canAddAlias(nic)).toBe(true);
        });
    });

    describe("canAddVLAN", function() {

        it("returns false if nic undefined", function() {
            var controller = makeController();
            expect($scope.canAddVLAN()).toBe(false);
        });

        it("returns false if nic type is alias", function() {
            var controller = makeController();
            var nic = {
                type: "alias"
            };
            expect($scope.canAddVLAN(nic)).toBe(false);
        });

        it("returns false if nic type is vlan", function() {
            var controller = makeController();
            var nic = {
                type: "vlan"
            };
            expect($scope.canAddVLAN(nic)).toBe(false);
        });

        it("returns false if no unused vlans", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1, 2, 3],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                },
                {
                    id: 2,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 1
                },
                {
                    id: 3,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 2
                }
            ];
            var nic = {
                id: 0,
                type: "physical",
                fabric: fabric
            };
            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            expect($scope.canAddVLAN(nic)).toBe(false);
        });

        it("returns true if unused vlans", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1, 2, 3],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                },
                {
                    id: 2,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 1
                }
            ];
            var nic = {
                id: 0,
                type: "physical",
                fabric: fabric
            };
            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            expect($scope.canAddVLAN(nic)).toBe(true);
        });
    });

    describe("canAddAnotherVLAN", function() {

        it("returns false if canAddVLAN returns false", function() {
            var controller = makeController();
            spyOn($scope, "canAddVLAN").and.returnValue(false);
            expect($scope.canAddAnotherVLAN()).toBe(false);
        });

        it("returns false if only 1 unused vlans", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1, 2, 3],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                },
                {
                    id: 2,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 1
                }
            ];
            var nic = {
                id: 0,
                type: "physical",
                fabric: fabric
            };
            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            expect($scope.canAddAnotherVLAN(nic)).toBe(false);
        });

        it("returns true if more than 1 unused vlans", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1, 2, 3],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                }
            ];
            var nic = {
                id: 0,
                type: "physical",
                fabric: fabric
            };
            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            expect($scope.canAddAnotherVLAN(nic)).toBe(true);
        });
    });

    describe("getRemoveTypeText", function() {

        it("returns interface for physical interface", function() {
            var controller = makeController();
            var nic = {
                type: "physical"
            };
            expect($scope.getRemoveTypeText(nic)).toBe("interface");
        });

        it("returns VLAN for VLAN interface", function() {
            var controller = makeController();
            var nic = {
                type: "vlan"
            };
            expect($scope.getRemoveTypeText(nic)).toBe("VLAN");
        });

        it("returns type for other types", function() {
            var controller = makeController();
            var type = makeName("type");
            var nic = {
                type: type
            };
            expect($scope.getRemoveTypeText(nic)).toBe(type);
        });
    });

    describe("remove", function() {

        it("sets selectedMode to delete", function() {
            var controller = makeController();
            $scope.remove();
            expect($scope.selectedMode).toBe("delete");
        });
    });

    describe("quickRemove", function() {

        it("selects interface and sets selectedMode to delete", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };
            $scope.quickRemove(nic);
            expect($scope.isInterfaceSelected(nic)).toBe(true);
            expect($scope.selectedMode).toBe("delete");
        });
    });

    describe("cancel", function() {

        it("clears newInterface and sets selectedMode to single", function() {
            var controller = makeController();
            var newInterface = {};
            $scope.newInterface = newInterface;
            $scope.selectedMode = "delete";
            $scope.cancel();
            expect($scope.newInterface).not.toBe(newInterface);
            expect($scope.selectedMode).toBe("single");
        });

        it("clears newBondInterface and sets selectedMode to multi",
            function() {
                var controller = makeController();
                var newBondInterface = {};
                $scope.newBondInterface = newBondInterface;
                $scope.selectedMode = "create-bond";
                $scope.cancel();
                expect($scope.newBondInterface).not.toBe(newBondInterface);
                expect($scope.selectedMode).toBe("multi");
            });
    });

    describe("confirmRemove", function() {

        it("sets selectedMode to none", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                type: "physical",
                link_id: makeInteger(0, 100)
            };
            $scope.toggleInterfaceSelect(nic);
            $scope.selectedMode = "delete";

            spyOn(NodesManager, "deleteInterface");
            $scope.confirmRemove(nic);

            expect($scope.selectedMode).toBeNull();
            expect($scope.selectedInterfaces).toEqual([]);
        });

        it("calls NodesManager.deleteInterface", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                type: "physical",
                link_id: makeInteger(0, 100)
            };
            $scope.toggleInterfaceSelect(nic);
            $scope.selectedMode = "delete";

            spyOn(NodesManager, "deleteInterface");
            $scope.confirmRemove(nic);

            expect(NodesManager.deleteInterface).toHaveBeenCalledWith(
                node, nic.id);
        });

        it("calls NodesManager.unlinkSubnet", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                type: "alias",
                link_id: makeInteger(0, 100)
            };
            $scope.toggleInterfaceSelect(nic);
            $scope.selectedMode = "delete";

            spyOn(NodesManager, "unlinkSubnet");
            $scope.confirmRemove(nic);

            expect(NodesManager.unlinkSubnet).toHaveBeenCalledWith(
                node, nic.id, nic.link_id);
        });

        it("removes nic from interfaces", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                type: "alias",
                link_id: makeInteger(0, 100)
            };
            $scope.interfaces = [nic];
            $scope.toggleInterfaceSelect(nic);
            $scope.selectedMode = "delete";

            spyOn(NodesManager, "unlinkSubnet");
            $scope.confirmRemove(nic);

            expect($scope.interfaces).toEqual([]);
        });
    });

    describe("add", function() {

        it("sets up newInterface for alias", function() {
            var controller = makeController();
            var vlan = {};
            var nic = {
                id: makeInteger(0, 100),
                type: "physical",
                link_id: makeInteger(0, 100),
                vlan: vlan
            };

            var subnet = {};
            spyOn(VLANsManager, "getSubnets").and.returnValue([subnet]);

            $scope.add('alias', nic);
            expect($scope.newInterface).toEqual({
                type: "alias",
                vlan: vlan,
                subnet: subnet,
                mode: "auto",
                parent: nic
            });
            expect($scope.newInterface.vlan).toBe(vlan);
            expect($scope.newInterface.subnet).toBe(subnet);
            expect($scope.newInterface.parent).toBe(nic);
            expect($scope.selectedMode).toBe("add");
        });

        it("sets up newInterface for vlan", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                }
            ];
            var nic = {
                id: 0,
                type: "physical",
                link_id: -1,
                fabric: fabric,
                vlan: vlans[0]
            };
            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            $scope.newInterface = {
                vlan: vlans[1]
            };

            $scope.add('vlan', nic);
            expect($scope.newInterface).toEqual({
                type: "vlan",
                vlan: vlans[2],
                subnet: null,
                mode: "link_up",
                parent: nic
            });
            expect($scope.newInterface.vlan).toBe(vlans[2]);
            expect($scope.newInterface.parent).toBe(nic);
            expect($scope.selectedMode).toBe("add");
        });
    });

    describe("quickAdd", function() {

        it("selects nic and calls add with alias", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };

            $scope.selectedInterfaces = [{}, {}, {}];
            spyOn($scope, "canAddAlias").and.returnValue(true);
            spyOn($scope, "add");

            $scope.quickAdd(nic);
            expect($scope.selectedInterfaces).toEqual(
                [$scope.getUniqueKey(nic)]);
            expect($scope.add).toHaveBeenCalledWith('alias', nic);
        });

        it("selects nic and calls add with vlan", function() {
            var controller = makeController();
            var nic = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100)
            };

            $scope.selectedInterfaces = [{}, {}, {}];
            spyOn($scope, "canAddAlias").and.returnValue(false);
            spyOn($scope, "add");

            $scope.quickAdd(nic);
            expect($scope.selectedInterfaces).toEqual(
                [$scope.getUniqueKey(nic)]);
            expect($scope.add).toHaveBeenCalledWith('vlan', nic);
        });
    });

    describe("getAddName", function() {

        it("returns alias name based on links length", function() {
            var controller = makeController();
            var name = makeName("eth");
            var parent = {
                id: makeInteger(0, 100),
                name: name,
                link_id: makeInteger(0, 100),
                links: [{}, {}, {}]
            };
            $scope.newInterface = {
                type: "alias",
                parent: parent
            };

            expect($scope.getAddName()).toBe(name + ":3");
        });

        it("returns VLAN name based on VLAN vid", function() {
            var controller = makeController();
            var name = makeName("eth");
            var vid = makeInteger(0, 100);
            var parent = {
                id: makeInteger(0, 100),
                name: name,
                link_id: makeInteger(0, 100)
            };
            $scope.newInterface = {
                type: "vlan",
                parent: parent,
                vlan: {
                    vid: vid
                }
            };

            expect($scope.getAddName()).toBe(name + "." + vid);
        });
    });

    describe("addTypeChanged", function() {

        it("reset properties based on the new type alias", function() {
            var controller = makeController();
            var vlan = {};
            var subnet = {};
            var parent = {
                id: makeInteger(0, 100),
                name: name,
                link_id: makeInteger(0, 100),
                vlan: vlan
            };
            spyOn(VLANsManager, "getSubnets").and.returnValue([subnet]);
            $scope.newInterface = {
                type: "alias",
                parent: parent
            };
            $scope.addTypeChanged();

            expect($scope.newInterface.vlan).toBe(vlan);
            expect($scope.newInterface.subnet).toBe(subnet);
            expect($scope.newInterface.mode).toBe("auto");
        });

        it("reset properties based on the new type VLAN", function() {
            var controller = makeController();
            var fabric = {
                id: 0
            };
            var vlans = [
                {
                    id: 0,
                    fabric: 0
                },
                {
                    id: 1,
                    fabric: 0
                },
                {
                    id: 2,
                    fabric: 0
                }
            ];
            var originalInterfaces = [
                {
                    id: 0,
                    type: "physical",
                    parents: [],
                    children: [1],
                    vlan_id: 0
                },
                {
                    id: 1,
                    type: "vlan",
                    parents: [0],
                    children: [],
                    vlan_id: 0
                }
            ];
            var parent = {
                id: 0,
                type: "physical",
                link_id: -1,
                fabric: fabric,
                vlan: vlans[0]
            };

            $scope.originalInterfaces = originalInterfaces;
            $scope.vlans = vlans;
            $scope.newInterface = {
                type: "vlan",
                parent: parent
            };
            $scope.addTypeChanged();

            expect($scope.newInterface.vlan).toBe(vlans[1]);
            expect($scope.newInterface.subnet).toBeNull();
            expect($scope.newInterface.mode).toBe("link_up");
        });
    });

    describe("addVLANChanged", function() {

        it("clears subnets on newInterface", function() {
            var controller = makeController();
            $scope.newInterface = {
                subnet: {}
            };
            $scope.addVLANChanged();
            expect($scope.newInterface.subnet).toBeNull();
        });
    });

    describe("addSubnetChanged", function() {

        it("sets mode to link_up if no subnet", function() {
            var controller = makeController();
            $scope.newInterface = {
                mode: "auto"
            };
            $scope.addSubnetChanged();
            expect($scope.newInterface.mode).toBe("link_up");
        });

        it("leaves mode to alone when subnet", function() {
            var controller = makeController();
            $scope.newInterface = {
                mode: "auto",
                subnet: {}
            };
            $scope.addSubnetChanged();
            expect($scope.newInterface.mode).toBe("auto");
        });
    });

    describe("addInterface", function() {

        it("calls saveInterfaceLink with correct params", function() {
            var controller = makeController();
            var parent = {
                id: makeInteger(0, 100)
            };
            var subnet = {};
            $scope.newInterface = {
                type: "alias",
                mode: "auto",
                subnet: subnet,
                parent: parent
            };
            $scope.selectedInterfaces = [{}];
            $scope.selectedMode = "add";
            spyOn($scope, "saveInterfaceLink");
            $scope.addInterface();
            expect($scope.saveInterfaceLink).toHaveBeenCalledWith({
                id: parent.id,
                mode: "auto",
                subnet: subnet,
                ip_address: ""
            });
            expect($scope.selectedMode).toBeNull();
            expect($scope.selectedInterfaces).toEqual([]);
            expect($scope.newInterface).toEqual({});
        });

        it("calls createVLANInterface with correct params", function() {
            var controller = makeController();
            var parent = {
                id: makeInteger(0, 100)
            };
            var vlan = {
                id: makeInteger(0, 100)
            };
            var subnet = {
                id: makeInteger(0, 100)
            };
            $scope.newInterface = {
                type: "vlan",
                mode: "auto",
                parent: parent,
                vlan: vlan,
                subnet: subnet
            };
            $scope.selectedInterfaces = [{}];
            $scope.selectedMode = "add";
            spyOn(NodesManager, "createVLANInterface").and.returnValue(
                $q.defer().promise);

            $scope.addInterface();
            expect(NodesManager.createVLANInterface).toHaveBeenCalledWith(
                node, {
                    parent: parent.id,
                    vlan: vlan.id,
                    mode: "auto",
                    subnet: subnet.id
                });
            expect($scope.selectedMode).toBeNull();
            expect($scope.selectedInterfaces).toEqual([]);
            expect($scope.newInterface).toEqual({});
        });

        it("calls add again with type", function() {
            var controller = makeController();
            var parent = {
                id: makeInteger(0, 100)
            };
            $scope.newInterface = {
                type: "alias",
                mode: "auto",
                subnet: {},
                parent: parent
            };
            var selection = [{}];
            $scope.selectedInterfaces = selection;
            $scope.selectedMode = "add";
            spyOn($scope, "saveInterfaceLink");
            spyOn($scope, "add");
            $scope.addInterface("alias");

            expect($scope.add).toHaveBeenCalledWith("alias", parent);
            expect($scope.selectedMode).toBe("add");
            expect($scope.selectedInterfaces).toBe(selection);
        });
    });

    describe("isDisabled", function() {

        it("returns false when in none, single, or multi mode", function() {
            var controller = makeController();
            $scope.selectedMode = null;
            expect($scope.isDisabled()).toBe(false);
            $scope.selectedMode = "single";
            expect($scope.isDisabled()).toBe(false);
            $scope.selectedMode = "multi";
            expect($scope.isDisabled()).toBe(false);
        });

        it("returns true when in delete, add, or create modes", function() {
            var controller = makeController();
            $scope.selectedMode = "create-bond";
            expect($scope.isDisabled()).toBe(true);
            $scope.selectedMode = "add";
            expect($scope.isDisabled()).toBe(true);
            $scope.selectedMode = "delete";
            expect($scope.isDisabled()).toBe(true);
        });
    });

    describe("canCreateBond", function() {

        it("returns false if not in multi mode", function() {
            var controller = makeController();
            var modes = [null, "add", "delete", "single", "delete"];
            angular.forEach(modes, function(mode) {
                $scope.selectedMode = mode;
                expect($scope.canCreateBond()).toBe(false);
            });
        });

        it("returns false if selected interface is bond", function() {
            var controller = makeController();
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "bond"
            };
            var nic2 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "bond"
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            expect($scope.canCreateBond()).toBe(false);
        });

        it("returns false if selected interface is alias", function() {
            var controller = makeController();
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "alias"
            };
            var nic2 = {
                id: makeInteger(101, 200),
                link_id: makeInteger(0, 100),
                type: "alias"
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            expect($scope.canCreateBond()).toBe(false);
        });

        it("returns false if not same selected vlan", function() {
            var controller = makeController();
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: {}
            };
            var nic2 = {
                id: makeInteger(101, 200),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: {}
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            expect($scope.canCreateBond()).toBe(false);
        });

        it("returns true if same selected vlan", function() {
            var controller = makeController();
            var vlan = {};
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            var nic2 = {
                id: makeInteger(101, 200),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            expect($scope.canCreateBond()).toBe(true);
        });
    });

    describe("isShowingCreateBond", function() {

        it("returns true in create-bond mode", function() {
            var controller = makeController();
            $scope.selectedMode = "create-bond";
            expect($scope.isShowingCreateBond()).toBe(true);
        });

        it("returns false in multi mode", function() {
            var controller = makeController();
            $scope.selectedMode = "multi";
            expect($scope.isShowingCreateBond()).toBe(false);
        });
    });

    describe("showCreateBond", function() {

        it("sets mode to create-bond", function() {
            var controller = makeController();
            $scope.selectedMode = "multi";
            spyOn($scope, "canCreateBond").and.returnValue(true);
            $scope.showCreateBond();
            expect($scope.selectedMode).toBe("create-bond");
        });

        it("creates the newBondInterface", function() {
            var controller = makeController();
            var vlan = {};
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            var nic2 = {
                id: makeInteger(101, 200),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            $scope.showCreateBond();
            expect($scope.newBondInterface).toEqual({
                name: "bond0",
                parents: [nic1, nic2],
                primary: nic1,
                macAddress: "",
                mode: "active-backup",
                lacpRate: "slow",
                xmitHashPolicy: "layer2"
            });
        });
    });

    describe("getBondPlaceholderMACAddress", function() {

        it("returns empty string if primary not set", function() {
            var controller = makeController();
            expect($scope.getBondPlaceholderMACAddress()).toBe("");
        });

        it("returns the MAC address of the primary interface", function() {
            var controller = makeController();
            var macAddress = makeName("mac");
            $scope.newBondInterface.primary = {
                mac_address: macAddress
            };
            expect($scope.getBondPlaceholderMACAddress()).toBe(macAddress);
        });
    });

    describe("isBondMACAddressInvalid", function() {

        it("returns false when the macAddress is blank", function() {
            var controller = makeController();
            $scope.newBondInterface.macAddress = "";
            expect($scope.isBondMACAddressInvalid()).toBe(false);
        });

        it("returns false if valid macAddress", function() {
            var controller = makeController();
            $scope.newBondInterface.macAddress = "00:11:22:33:44:55";
            expect($scope.isBondMACAddressInvalid()).toBe(false);
        });

        it("returns true if invalid macAddress", function() {
            var controller = makeController();
            $scope.newBondInterface.macAddress = "00:11:22:33:44";
            expect($scope.isBondMACAddressInvalid()).toBe(true);
        });
    });

    describe("showLACPRate", function() {

        it("returns true if in 802.3ad mode", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = "802.3ad";
            expect($scope.showLACPRate()).toBe(true);
        });

        it("returns false if not in 802.3ad mode", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = makeName("otherMode");
            expect($scope.showLACPRate()).toBe(false);
        });
    });

    describe("showXMITHashPolicy", function() {

        it("returns true if in balance-xor mode", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = "balance-xor";
            expect($scope.showXMITHashPolicy()).toBe(true);
        });

        it("returns true if in 802.3ad mode", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = "802.3ad";
            expect($scope.showXMITHashPolicy()).toBe(true);
        });

        it("returns true if in balance-tlb mode", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = "balance-tlb";
            expect($scope.showXMITHashPolicy()).toBe(true);
        });

        it("returns false if not in other modes", function() {
            var controller = makeController();
            $scope.newBondInterface.mode = makeName("otherMode");
            expect($scope.showXMITHashPolicy()).toBe(false);
        });
    });

    describe("addBond", function() {

        it("calls createBondInterface and removes selection", function() {
            var controller = makeController();
            var vlan = {
                id: makeInteger(0, 100)
            };
            var nic1 = {
                id: makeInteger(0, 100),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            var nic2 = {
                id: makeInteger(101, 200),
                link_id: makeInteger(0, 100),
                type: "physical",
                vlan: vlan
            };
            $scope.interfaces = [nic1, nic2];
            $scope.interfaceLinksMap = {};
            $scope.interfaceLinksMap[nic1.id] = {};
            $scope.interfaceLinksMap[nic1.id][nic1.link_id] = nic1;
            $scope.interfaceLinksMap[nic2.id] = {};
            $scope.interfaceLinksMap[nic2.id][nic2.link_id] = nic2;
            $scope.toggleInterfaceSelect(nic1);
            $scope.toggleInterfaceSelect(nic2);
            $scope.showCreateBond();

            spyOn(NodesManager, "createBondInterface").and.returnValue(
                $q.defer().promise);
            $scope.newBondInterface.name = "bond0";
            $scope.newBondInterface.macAddress = "00:11:22:33:44:55";
            $scope.addBond();

            expect(NodesManager.createBondInterface).toHaveBeenCalledWith(
                node, {
                    name: "bond0",
                    mac_address: "00:11:22:33:44:55",
                    parents: [nic1.id, nic2.id],
                    vlan: vlan.id,
                    bond_mode: "active-backup",
                    bond_lacp_rate: "slow",
                    bond_xmit_hash_policy: "layer2"
                });
            expect($scope.interfaces).toEqual([]);
            expect($scope.newBondInterface).toEqual({});
            expect($scope.selectedInterfaces).toEqual([]);
            expect($scope.selectedMode).toBeNull();
        });
    });
});
