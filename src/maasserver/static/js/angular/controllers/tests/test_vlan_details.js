/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubentsListController.
 */

describe("VLANDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Make a fake VLAN
    function makeVLAN() {
        var vlan = {
            id: makeInteger(1, 10000),
            vid: makeInteger(1, 4095),
            fabric: 1,
            name: null
        };
        VLANsManager._items.push(vlan);
        return vlan;
    }

    // Make a fake fabric
    function makeFabric() {
        var fabric = {
            id: 1,
            name: 'fabric-0'
        };
        FabricsManager._items.push(fabric);
        return fabric;
    }

    // Grab the needed angular pieces.
    var $controller, $rootScope, $filter, $location, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $filter = $injector.get("$filter");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
    }));

    // Load any injected managers and services.
    var VLANsManager, SubnetsManager, SpacesManager, FabricsManager;
    var ControllersManager, ManagerHelperService, ErrorService;
    beforeEach(inject(function($injector) {
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        SpacesManager = $injector.get("SpacesManager");
        FabricsManager = $injector.get("FabricsManager");
        ControllersManager = $injector.get("ControllersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
    }));

    var vlan, fabric, $routeParams;
    beforeEach(function() {
        vlan = makeVLAN();
        fabric = makeFabric();
        $routeParams = {
            vlan_id: vlan.id
        };
    });

    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("VLANDetailsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $filter: $filter,
            $location: $location,
            VLANsManager: VLANsManager,
            SubnetsManager: SubnetsManager,
            SpacesManager: SpacesManager,
            FabricsManager: FabricsManager,
            ControllersManager: ControllersManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });

        return controller;
    }

    // Make the controller and resolve the setActiveItem call.
    function makeControllerResolveSetActiveItem() {
        var setActiveDefer = $q.defer();
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(vlan);
        $rootScope.$digest();

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("networks");
    });

    it("calls loadManagers with required managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
            [VLANsManager, SubnetsManager, SpacesManager, FabricsManager,
                ControllersManager]);
    });

    it("raises error if vlan identifier is invalid", function() {
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        spyOn(ErrorService, "raiseError").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.vlan_id = 'xyzzy';

        defer.resolve();
        $rootScope.$digest();

        expect($scope.vlan).toBe(null);
        expect($scope.loaded).toBe(false);
        expect(VLANsManager.setActiveItem).not.toHaveBeenCalled();
        expect(ErrorService.raiseError).toHaveBeenCalled();
    });

    it("doesn't call setActiveItem if vlan is loaded", function() {
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        VLANsManager._activeItem = vlan;
        $routeParams.vlan_id = vlan.id;

        defer.resolve();
        $rootScope.$digest();

        expect($scope.vlan).toBe(vlan);
        expect($scope.loaded).toBe(true);
        expect(VLANsManager.setActiveItem).not.toHaveBeenCalled();
    });

    it("calls setActiveItem if vlan is not active", function() {
        spyOn(VLANsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.vlan_id = vlan.id;

        defer.resolve();
        $rootScope.$digest();

        expect(VLANsManager.setActiveItem).toHaveBeenCalledWith(
            vlan.id);
    });

    it("sets vlan and loaded once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($scope.vlan).toBe(vlan);
        expect($scope.loaded).toBe(true);
    });

    it("title is updated once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect(vlan.title).toBe("VLAN " + vlan.vid + " in " + fabric.name);
    });
});
