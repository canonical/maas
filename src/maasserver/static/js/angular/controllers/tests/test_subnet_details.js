/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubnetsListController.
 */

describe("SubnetDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Make a fake fabric
    function makeFabric() {
        var fabric = {
            id: 0,
            name: "fabric-0"
        };
        FabricsManager._items.push(fabric);
    }

    function makeVLAN() {
        var vlan = {
            id: 0,
            fabric: 0,
            vid: 0
        };
        VLANsManager._items.push(vlan);
    }

    function makeSpace() {
        var space = {
            id: 0,
            name: "default"
        };
        SpacesManager._items.push(space);
    }

    // Make a fake subnet
    function makeSubnet() {
        var subnet = {
            id: makeInteger(1, 10000),
            cidr: '169.254.0.0/24',
            name: 'Link Local',
            vlan: 0,
            dns_servers: []
        };
        SubnetsManager._items.push(subnet);
        return subnet;
    }

    function makeIPRange() {
        var iprange = {
            id: makeInteger(1, 10000),
            subnet: subnet.id
        };
        IPRangesManager._items.push(iprange);
        return iprange;
    }

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope, $q, $routeParams, $filter;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
        $location = $injector.get("$filter");
    }));

    // Load any injected managers and services.
    var SubnetsManager, IPRangesManager, SpacesManager, VLANsManager;
    var FabricsManager, UsersManager, HelperService, ErrorService;
    var ConverterService;
    beforeEach(inject(function($injector) {
        SubnetsManager = $injector.get("SubnetsManager");
        IPRangesManager = $injector.get("IPRangesManager");
        SpacesManager = $injector.get("SpacesManager");
        VLANsManager = $injector.get("VLANsManager");
        FabricsManager = $injector.get("FabricsManager");
        UsersManager = $injector.get("UsersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
        ConverterService = $injector.get("ConverterService");
    }));

    var fabric, vlan, space, subnet;
    beforeEach(function() {
        fabric = makeFabric();
        vlan = makeVLAN();
        space = makeSpace();
        subnet = makeSubnet();
    });

    // Makes the NodesListController
    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("SubnetDetailsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
            SubnetsManager: SubnetsManager,
            IPRangesManager: IPRangesManager,
            SpacesManager: SpacesManager,
            VLANsManager: VLANsManager,
            FabricsManager: FabricsManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });

        return controller;
    }

    // Make the controller and resolve the setActiveItem call.
    function makeControllerResolveSetActiveItem() {
        var setActiveDefer = $q.defer();
        spyOn(SubnetsManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.subnet_id = subnet.id;

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(subnet);
        $rootScope.$digest();

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("networks");
    });

    it("calls loadManagers with required managers" +
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith([
                SubnetsManager, IPRangesManager, SpacesManager, VLANsManager,
                FabricsManager
            ]);
    });

    it("raises error if subnet identifier is invalid", function() {
        spyOn(SubnetsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        spyOn(ErrorService, "raiseError").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.subnet_id = 'xyzzy';

        defer.resolve();
        $rootScope.$digest();

        expect($scope.subnet).toBe(null);
        expect($scope.loaded).toBe(false);
        expect(SubnetsManager.setActiveItem).not.toHaveBeenCalled();
        expect(ErrorService.raiseError).toHaveBeenCalled();
    });

    it("doesn't call setActiveItem if subnet is loaded", function() {
        spyOn(SubnetsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        SubnetsManager._activeItem = subnet;
        $routeParams.subnet_id = subnet.id;

        defer.resolve();
        $rootScope.$digest();

        expect($scope.subnet).toBe(subnet);
        expect($scope.loaded).toBe(true);
        expect(SubnetsManager.setActiveItem).not.toHaveBeenCalled();
    });

    it("calls setActiveItem if subnet is not active", function() {
        spyOn(SubnetsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.subnet_id = subnet.id;

        defer.resolve();
        $rootScope.$digest();

        expect(SubnetsManager.setActiveItem).toHaveBeenCalledWith(
            subnet.id);
    });

    it("sets subnet and loaded once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($scope.subnet).toBe(subnet);
        expect($scope.loaded).toBe(true);
    });

    it("title is updated once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($rootScope.title).toBe(subnet.cidr + " (" + subnet.name + ")");
    });

    describe("ipSort", function() {

        it("calls ipv4ToInteger when ipVersion == 4", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.ipVersion = 4;
            var expected = {};
            spyOn(ConverterService, "ipv4ToInteger").and.returnValue(expected);
            var ipAddress = {
                ip: {}
            };
            var observed = $scope.ipSort(ipAddress);
            expect(ConverterService.ipv4ToInteger).toHaveBeenCalledWith(
                ipAddress.ip);
            expect(observed).toBe(expected);
        });

        it("calls ipv6Expand when ipVersion == 6", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.ipVersion = 6;
            var expected = {};
            spyOn(ConverterService, "ipv6Expand").and.returnValue(expected);
            var ipAddress = {
                ip: {}
            };
            var observed = $scope.ipSort(ipAddress);
            expect(ConverterService.ipv6Expand).toHaveBeenCalledWith(
                ipAddress.ip);
            expect(observed).toBe(expected);
        });

        it("is predicate default", function() {
            var controller = makeControllerResolveSetActiveItem();
            expect($scope.predicate).toBe($scope.ipSort);
        });
    });

    describe("getAllocType", function() {

        var scenarios = {
            0: 'Automatic',
            1: 'Static',
            4: 'User reserved',
            5: 'DHCP',
            6: 'Observed',
            7: 'Unknown'
        };

        angular.forEach(scenarios, function(expected, allocType) {
            it("allocType( " + allocType + ") = " + expected, function() {
                var controller = makeControllerResolveSetActiveItem();
                expect($scope.getAllocType(allocType)).toBe(expected);
            });
        });
    });

    describe("allocTypeSort", function() {

        it("calls getAllocType", function() {
            var controller = makeControllerResolveSetActiveItem();
            var expected = {};
            spyOn($scope, "getAllocType").and.returnValue(expected);
            var ipAddress = {
                alloc_type: {}
            };
            var observed = $scope.allocTypeSort(ipAddress);
            expect($scope.getAllocType).toHaveBeenCalledWith(
                ipAddress.alloc_type);
            expect(observed).toBe(expected);
        });
    });

    describe("getNodeType", function() {

        var scenarios = {
            0: 'Machine',
            1: 'Device',
            2: 'Rack controller',
            3: 'Region controller',
            4: 'Rack and region controller',
            5: 'Unknown'
        };

        angular.forEach(scenarios, function(expected, nodeType) {
            it("nodeType( " + nodeType + ") = " + expected, function() {
                var controller = makeControllerResolveSetActiveItem();
                expect($scope.getNodeType(nodeType)).toBe(expected);
            });
        });
    });

    describe("nodeTypeSort", function() {

        it("calls getNodeType", function() {
            var controller = makeControllerResolveSetActiveItem();
            var expected = {};
            spyOn($scope, "getNodeType").and.returnValue(expected);
            var ipAddress = {
                node_summary: {
                    node_type: {}
                }
            };
            var observed = $scope.nodeTypeSort(ipAddress);
            expect($scope.getNodeType).toHaveBeenCalledWith(
                ipAddress.node_summary.node_type);
            expect(observed).toBe(expected);
        });
    });

    describe("ownerSort", function() {

        it("returns owner", function() {
            var controller = makeControllerResolveSetActiveItem();
            var ipAddress = {
                user: makeName("owner")
            };
            var observed = $scope.ownerSort(ipAddress);
            expect(observed).toBe(ipAddress.user);
        });

        it("returns MAAS for empty string", function() {
            var controller = makeControllerResolveSetActiveItem();
            var ipAddress = {
                user: ""
            };
            var observed = $scope.ownerSort(ipAddress);
            expect(observed).toBe("MAAS");
        });

        it("returns MAAS for null", function() {
            var controller = makeControllerResolveSetActiveItem();
            var ipAddress = {
                user: null
            };
            var observed = $scope.ownerSort(ipAddress);
            expect(observed).toBe("MAAS");
        });
    });

    describe("sortIPTable", function() {

        it("sets predicate and inverts reverse", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.reverse = true;
            var predicate = {};
            $scope.sortIPTable(predicate);
            expect($scope.predicate).toBe(predicate);
            expect($scope.reverse).toBe(false);
            $scope.sortIPTable(predicate);
            expect($scope.reverse).toBe(true);
        });
    });

    describe("deleteButton", function() {

        it("confirms delete", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.deleteButton();
            expect($scope.confirmingDelete).toBe(true);
        });

        it("clears error", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.error = makeName("error");
            $scope.deleteButton();
            expect($scope.error).toBeNull();
        });
    });

    describe("cancelDeleteButton", function() {

        it("cancels delete", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.deleteButton();
            $scope.cancelDeleteButton();
            expect($scope.confirmingDelete).toBe(false);
        });
    });

    describe("deleteSubnet", function() {

        it("calls deleteSubnet", function() {
            var controller = makeController();
            var deleteSubnet = spyOn(SubnetsManager, "deleteSubnet");
            var defer = $q.defer();
            deleteSubnet.and.returnValue(defer.promise);
            $scope.deleteConfirmButton();
            expect(deleteSubnet).toHaveBeenCalled();
        });
    });

    describe("subnetPreSave", function() {

        it("updates vlan when fabric changed", function() {
            var controller = makeController();
            var vlan = {
                id: makeInteger(0, 100)
            };
            var fabric = {
                id: makeInteger(0, 100),
                default_vlan_id: vlan.id,
                vlan_ids: [vlan.id]
            };
            FabricsManager._items.push(fabric);
            var subnet = {
                fabric: fabric.id
            };
            var updatedSubnet = $scope.subnetPreSave(subnet, ['fabric']);
            expect(updatedSubnet.vlan).toBe(vlan.id);
        });
    });

    describe("addRange", function() {

        it("reserved", function() {
            var controller = makeController();
            $scope.subnet = {
                id: makeInteger(0, 100)
            };
            $scope.addRange('reserved');
            expect($scope.newRange).toEqual({
                type: 'reserved',
                subnet: $scope.subnet.id,
                start_ip: "",
                end_ip: "",
                comment: ""
            });
        });

        it("dynamic", function() {
            var controller = makeController();
            $scope.subnet = {
                id: makeInteger(0, 100)
            };
            $scope.addRange('dynamic');
            expect($scope.newRange).toEqual({
                type: 'dynamic',
                subnet: $scope.subnet.id,
                start_ip: "",
                end_ip: "",
                comment: "Dynamic"
            });
        });
    });

    describe("cancelAddRange", function() {

        it("clears newRange", function() {
            var controller = makeController();
            $scope.newRange = {};
            $scope.cancelAddRange();
            expect($scope.newRange).toBeNull();
        });
    });

    describe("ipRangeCanBeModified", function() {

        it("returns true for super user", function() {
            var controller = makeController();
            var range = {
                type: "dynamic"
            };
            spyOn($scope, "isSuperUser").and.returnValue(true);
            expect($scope.ipRangeCanBeModified(range)).toBe(true);
        });

        it("returns false for standard user and dynamic", function() {
            var controller = makeController();
            var range = {
                type: "dynamic"
            };
            spyOn($scope, "isSuperUser").and.returnValue(false);
            expect($scope.ipRangeCanBeModified(range)).toBe(false);
        });

        it("returns false for standard user who is not owner", function() {
            var controller = makeController();
            var user = {
                id: makeInteger(0, 100)
            };
            var range = {
                type: "reserved",
                user: makeInteger(101, 200)
            };
            spyOn(UsersManager, "getAuthUser").and.returnValue(user);
            spyOn($scope, "isSuperUser").and.returnValue(false);
            expect($scope.ipRangeCanBeModified(range)).toBe(false);
        });

        it("returns true for standard user who is owner", function() {
            var controller = makeController();
            var user = {
                id: makeInteger(0, 100)
            };
            var range = {
                type: "reserved",
                user: user.id
            };
            spyOn(UsersManager, "getAuthUser").and.returnValue(user);
            spyOn($scope, "isSuperUser").and.returnValue(false);
            expect($scope.ipRangeCanBeModified(range)).toBe(true);
        });
    });

    describe("isIPRangeInEditMode", function() {

        it("returns true when editIPRange", function() {
            var controller = makeController();
            var range = {};
            $scope.editIPRange = range;
            expect($scope.isIPRangeInEditMode(range)).toBe(true);
        });

        it("returns false when editIPRange", function() {
            var controller = makeController();
            var range = {};
            $scope.editIPRange = range;
            expect($scope.isIPRangeInEditMode({})).toBe(false);
        });
    });

    describe("ipRangeToggleEditMode", function() {

        it("clears deleteIPRange", function() {
            var controller = makeController();
            $scope.deleteIPRange = {};
            $scope.ipRangeToggleEditMode({});
            expect($scope.deleteIPRange).toBeNull();
        });

        it("clears editIPRange when already set", function() {
            var controller = makeController();
            var range = {};
            $scope.editIPRange = range;
            $scope.ipRangeToggleEditMode(range);
            expect($scope.editIPRange).toBeNull();
        });

        it("sets editIPRange when different range", function() {
            var controller = makeController();
            var range = {};
            var otherRange = {};
            $scope.editIPRange = otherRange;
            $scope.ipRangeToggleEditMode(range);
            expect($scope.editIPRange).toBe(range);
        });
    });

    describe("isIPRangeInDeleteMode", function() {

        it("return true when deleteIPRange is same", function() {
            var controller = makeController();
            var range = {};
            $scope.deleteIPRange = range;
            expect($scope.isIPRangeInDeleteMode(range)).toBe(true);
        });

        it("return false when deleteIPRange is different", function() {
            var controller = makeController();
            var range = {};
            $scope.deleteIPRange = range;
            expect($scope.isIPRangeInDeleteMode({})).toBe(false);
        });
    });

    describe("ipRangeEnterDeleteMode", function() {

        it("clears editIPRange and sets deleteIPRange", function() {
            var controller = makeController();
            var range = {};
            $scope.editIPRange = {};
            $scope.ipRangeEnterDeleteMode(range);
            expect($scope.editIPRange).toBeNull();
            expect($scope.deleteIPRange).toBe(range);
        });
    });

    describe("ipRangeCancelDelete", function() {

        it("clears deleteIPRange", function() {
            var controller = makeController();
            $scope.deleteIPRange = {};
            $scope.ipRangeCancelDelete();
            expect($scope.deleteIPRange).toBeNull();
        });
    });

    describe("ipRangeConfirmDelete", function() {

        it("calls deleteItem and clears deleteIPRange on resolve", function() {
            var controller = makeController();
            var range = {};
            $scope.deleteIPRange = range;

            var defer = $q.defer();
            spyOn(IPRangesManager, "deleteItem").and.returnValue(
                defer.promise);
            $scope.ipRangeConfirmDelete();

            expect(IPRangesManager.deleteItem).toHaveBeenCalledWith(range);
            defer.resolve();
            $scope.$digest();

            expect($scope.deleteIPRange).toBeNull();
        });
    });
});
