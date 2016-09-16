/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for IntroController.
 */

// Global maas config.
MAAS_config = {};

describe("IntroController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope, $q, $window;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
        $window = {
            location: {
                reload: jasmine.createSpy("reload")
            }
        };
    }));

    // Load any injected managers and services.
    var ConfigsManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        ConfigsManager = $injector.get("ConfigsManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Before the test mark it as not complete, after each test mark
    // it as complete.
    beforeEach(function() {
        window.MAAS_config.completed_intro = false;
    });
    afterEach(function() {
        window.MAAS_config.completed_intro = true;
    });

    // Makes the IntroController
    function makeController(loadManagerDefer) {
        var loadManager = spyOn(ManagerHelperService, "loadManager");
        if(angular.isObject(loadManagerDefer)) {
            loadManager.and.returnValue(loadManagerDefer.promise);
        } else {
            loadManager.and.returnValue($q.defer().promise);
        }

        // Create the controller.
        var controller = $controller("IntroController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $window: $window,
            $location: $location,
            ConfigsManager: ConfigsManager,
            ManagerHelperService: ManagerHelperService
        });

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Welcome");
        expect($rootScope.page).toBe("intro");
    });

    it("calls loadManagers with correct managers", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
            ConfigsManager);
    });

    it("sets initial $scope", function() {
        var controller = makeController();
        expect($scope.loading).toBe(true);
    });

    it("clears loading", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $scope.$digest();
        expect($scope.loading).toBe(false);
    });

    it("calls $location.path if already completed", function() {
        window.MAAS_config.completed_intro = true;
        spyOn($location, 'path');
        var controller = makeController();
        expect($location.path).toHaveBeenCalledWith('/');
    });

    describe("$rootScope.skip", function() {

        it("calls updateItem and reloads", function() {
            var controller = makeController();
            var defer = $q.defer();
            spyOn(ConfigsManager, "updateItem").and.returnValue(defer.promise);
            $rootScope.skip();

            expect(ConfigsManager.updateItem).toHaveBeenCalledWith({
                'name': 'completed_intro',
                'value': true
            });
            defer.resolve();
            $scope.$digest();
            expect($window.location.reload).toHaveBeenCalled();
        });
    });
});
