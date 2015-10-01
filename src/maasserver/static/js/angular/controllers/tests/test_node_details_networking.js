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
        expect($scope.fabrics).toBe(FabricsManager.getItems());
        expect($scope.vlans).toBe(VLANsManager.getItems());
        expect($scope.subnets).toBe(SubnetsManager.getItems());
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
            "link_up": "No IP",
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
                    "text": "No IP"
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
                    "text": "No IP"
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
});
