/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodesListController.
 */

// Make a fake user.
var userId = 0;
function makeUser() {
    return {
        id: userId++,
        username: makeName("username"),
        first_name: makeName("first_name"),
        last_name: makeName("last_name"),
        email: makeName("email"),
        is_superuser: false,
        sshkeys_count: 0
    };
}

describe("PodDetailsController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $location, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $location = $injector.get("$location");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
    }));

    // Load the required managers.
    var PodsManager, UsersManager, GeneralManager, ManagerHelperService;
    var ErrorService;
    beforeEach(inject(function($injector) {
        PodsManager = $injector.get("PodsManager");
        UsersManager = $injector.get("UsersManager");
        GeneralManager = $injector.get("GeneralManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
    }));

    // Mock the websocket connection to the region
    var RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        RegionConnection = $injector.get("RegionConnection");
        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Makes a fake node/device.
    var podId = 0;
    function makePod() {
        var pod = {
            id: podId++,
            $selected: false
        };
        PodsManager._items.push(pod);
        return pod;
    }

    // Create the pod that will be used and set the routeParams.
    var pod, $routeParams;
    beforeEach(function() {
        pod = makePod();
        $routeParams = {
            id: pod.id
        };
    });

    // Makes the PodsListController
    function makeController(loadManagersDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        // Create the controller.
        var controller = $controller("PodDetailsController", {
            $scope: $scope,
            $rootScope: $rootScope,
            $location: $location,
            $routeParams: $routeParams,
            PodsManager: PodsManager,
            UsersManager: UsersManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService
        });

        return controller;
    }

    // Make the controller and resolve the setActiveItem call.
    function makeControllerResolveSetActiveItem() {
        var setActiveDefer = $q.defer();
        spyOn(PodsManager, "setActiveItem").and.returnValue(
            setActiveDefer.promise);
        var defer = $q.defer();
        var controller = makeController(defer);

        defer.resolve();
        $rootScope.$digest();
        setActiveDefer.resolve(pod);
        $rootScope.$digest();

        return controller;
    }

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Loading...");
        expect($rootScope.page).toBe("pods");
    });

    it("sets initial values on $scope", function() {
        // tab-independent variables.
        var controller = makeController();
        expect($scope.pod).toBeNull();
        expect($scope.loaded).toBe(false);
        expect($scope.action.option).toBeNull();
        expect($scope.action.inProgress).toBe(false);
        expect($scope.action.error).toBeNull();
        expect($scope.powerTypes).toBe(GeneralManager.getData('power_types'));
    });

    it("calls loadManagers with PodsManager, UsersManager, GeneralManager",
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                $scope, [PodsManager, GeneralManager, UsersManager]);
        });

    it("sets loaded and title when loadManagers resolves", function() {
        var controller = makeControllerResolveSetActiveItem();
        expect($scope.loaded).toBe(true);
        expect($scope.title).toBe('Pod ' + pod.name);
    });

    describe("isSuperUser", function() {
        it("returns true if the user is a superuser", function() {
            var controller = makeController();
            spyOn(UsersManager, "getAuthUser").and.returnValue(
                { is_superuser: true });
            expect($scope.isSuperUser()).toBe(true);
        });

        it("returns false if the user is not a superuser", function() {
            var controller = makeController();
            spyOn(UsersManager, "getAuthUser").and.returnValue(
                { is_superuser: false });
            expect($scope.isSuperUser()).toBe(false);
        });
    });

    describe("isActionError", function() {

        it("returns false if not action error", function() {
            var controller = makeController();
            expect($scope.isActionError()).toBe(false);
        });

        it("returns true if action error", function() {
            var controller = makeController();
            $scope.action.error = makeName("error");
            expect($scope.isActionError()).toBe(true);
        });
    });

    describe("actionOptionChanged", function() {

        it("clears action error", function() {
            var controller = makeController();
            $scope.action.error = makeName("error");
            $scope.actionOptionChanged();
            expect($scope.action.error).toBeNull();
        });
    });

    describe("actionCancel", function() {

        it("clears action error and option", function() {
            var controller = makeController();
            $scope.action.error = makeName("error");
            $scope.action.option = {};
            $scope.actionCancel();
            expect($scope.action.error).toBeNull();
            expect($scope.action.option).toBeNull();
        });
    });

    describe("actionGo", function() {

        it("performs action and sets and clears inProgress", function() {
            var controller = makeControllerResolveSetActiveItem();
            var defer = $q.defer();
            var refresh = jasmine.createSpy('refresh');
            refresh.and.returnValue(defer.promise);
            $scope.action.option = {
                operation: refresh
            };
            $scope.action.error = makeName("error");
            $scope.actionGo();
            expect($scope.action.inProgress).toBe(true);
            expect(refresh).toHaveBeenCalledWith(pod);

            defer.resolve();
            $scope.$digest();
            expect($scope.action.inProgress).toBe(false);
            expect($scope.action.option).toBeNull();
            expect($scope.action.error).toBeNull();
        });

        it("performs action and sets error", function() {
            var controller = makeControllerResolveSetActiveItem();
            var defer = $q.defer();
            var refresh = jasmine.createSpy('refresh');
            refresh.and.returnValue(defer.promise);
            $scope.action.option = {
                operation: refresh
            };
            $scope.actionGo();
            expect($scope.action.inProgress).toBe(true);
            expect(refresh).toHaveBeenCalledWith(pod);

            var error = makeName("error");
            defer.reject(error);
            $scope.$digest();
            expect($scope.action.inProgress).toBe(false);
            expect($scope.action.option).not.toBeNull();
            expect($scope.action.error).toBe(error);
        });

        it("changes path to pods listing on delete", function() {
            var controller = makeControllerResolveSetActiveItem();
            var defer = $q.defer();
            var refresh = jasmine.createSpy('refresh');
            refresh.and.returnValue(defer.promise);
            $scope.action.option = {
                name: 'delete',
                operation: refresh
            };

            spyOn($location, "path");
            $scope.actionGo();
            defer.resolve();
            $rootScope.$digest();
            expect($location.path).toHaveBeenCalledWith("/pods");
        });
    });
});
