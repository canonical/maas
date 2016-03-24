/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for FabricsListController.
 */

describe("FabricDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Make a fake fabric
    function makeFabric() {
        var fabric = {
            id: makeInteger(1, 10000),
            name: makeName("fabric")
        };
        FabricsManager._items.push(fabric);
        return fabric;
    }

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope, $q, $routeParams;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $routeParams = {};
    }));

    // Load any injected managers and services.
    var FabricsManager, VLANsManager, SubnetsManager, SpacesManager;
    var ControllersManager, UsersManager, ManagerHelperService, ErrorService;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
        SubnetsManager = $injector.get("SubnetsManager");
        SpacesManager = $injector.get("SpacesManager");
        ControllersManager = $injector.get("ControllersManager");
        UsersManager = $injector.get("UsersManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
    }));

    var fabric;
    beforeEach(function() {
        fabric = makeFabric();
    });

    // Makes the NodesListController
    function makeController(loadManagerDefer) {
        spyOn(UsersManager, "isSuperUser").and.returnValue(true);
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagerDefer)) {
            loadManagers.and.returnValue(loadManagerDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("FabricDetailsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $routeParams: $routeParams,
            $location: $location,
            FabricsManager: FabricsManager,
            VLANsManager: VLANsManager,
            SubnetsManager: SubnetsManager,
            SpacesManager: SpacesManager,
            ControllersManager: ControllersManager,
            UsersManager: UsersManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });

        return controller;
    }

    // Make the controller and resolve the setActiveItem call.
    function makeControllerResolveSetActiveItem() {
        var setActiveDefer = $q.defer();
        spyOn(FabricsManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.fabric_id = fabric.id;

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(fabric);
        $rootScope.$digest();

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("fabrics");
    });

    it("calls loadManagers with correct managers" +
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith([
                FabricsManager, VLANsManager, SubnetsManager,
                SpacesManager, ControllersManager, UsersManager]);
    });

    it("raises error if fabric identifier is invalid", function() {
        spyOn(FabricsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        spyOn(ErrorService, "raiseError").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.fabric_id = 'xyzzy';

        defer.resolve();
        $rootScope.$digest();

        expect($scope.fabric).toBe(null);
        expect($scope.loaded).toBe(false);
        expect(FabricsManager.setActiveItem).not.toHaveBeenCalled();
        expect(ErrorService.raiseError).toHaveBeenCalled();
    });

    it("doesn't call setActiveItem if fabric is loaded", function() {
        spyOn(FabricsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        FabricsManager._activeItem = fabric;
        $routeParams.fabric_id = fabric.id;

        defer.resolve();
        $rootScope.$digest();

        expect($scope.fabric).toBe(fabric);
        expect($scope.loaded).toBe(true);
        expect(FabricsManager.setActiveItem).not.toHaveBeenCalled();
    });

    it("calls setActiveItem if fabric is not active", function() {
        spyOn(FabricsManager, "setActiveItem").and.returnValue(
            $q.defer().promise);
        var defer = $q.defer();
        var controller = makeController(defer);
        $routeParams.fabric_id = fabric.id;

        defer.resolve();
        $rootScope.$digest();

        expect(FabricsManager.setActiveItem).toHaveBeenCalledWith(
            fabric.id);
    });

    it("sets fabric and loaded once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($scope.fabric).toBe(fabric);
        expect($scope.loaded).toBe(true);
    });

    it("title is updated once setActiveItem resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($rootScope.title).toBe(fabric.name);
    });

    it("default fabric title is not special", function() {
        fabric.id = 0;
        var controller = makeControllerResolveSetActiveItem();
        expect($rootScope.title).toBe(fabric.name);
    });

    describe("canBeDeleted", function() {

        it("returns false if fabric is null", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.fabric = null;
            expect($scope.canBeDeleted()).toBe(false);
        });

        it("returns false if fabric is default fabric", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.fabric.id = 0;
            expect($scope.canBeDeleted()).toBe(false);
        });

        it("returns true if fabric is not default fabric", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.fabric.id = 1;
            expect($scope.canBeDeleted()).toBe(true);
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

    describe("deleteFabric", function() {

        it("calls deleteFabric", function() {
            var controller = makeController();
            var deleteFabric = spyOn(FabricsManager, "deleteFabric");
            var defer = $q.defer();
            deleteFabric.and.returnValue(defer.promise);
            $scope.deleteConfirmButton();
            expect(deleteFabric).toHaveBeenCalled();
        });
    });

});
