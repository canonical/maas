/* Copyright 2015 Canonical Ltd.  This software is licensed under the
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
    var FabricsManager, ManagerHelperService, ErrorService;
    beforeEach(inject(function($injector) {
        SubnetsManager = $injector.get("SubnetsManager");
        IPRangesManager = $injector.get("IPRangesManager");
        SpacesManager = $injector.get("SpacesManager");
        VLANsManager = $injector.get("VLANsManager");
        FabricsManager = $injector.get("FabricsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
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

    it("updates all_dns_servers when dns_servers changes", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($scope.subnet.dns_servers).toEqual([]);
        expect($scope.all_dns_servers).toBe("");
        $scope.subnet.dns_servers.push("127.0.0.1");
        $scope.$digest();
        expect($scope.subnet.dns_servers).toEqual(["127.0.0.1"]);
        expect($scope.all_dns_servers).toBe("127.0.0.1");
        $scope.subnet.dns_servers.push("127.0.0.2");
        $scope.$digest();
        expect($scope.subnet.dns_servers).toEqual(["127.0.0.1", "127.0.0.2"]);
        expect($scope.all_dns_servers).toBe("127.0.0.1 127.0.0.2");
    });
});
