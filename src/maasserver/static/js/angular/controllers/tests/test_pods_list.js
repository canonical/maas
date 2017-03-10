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

describe("PodsListController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $scope = $rootScope.$new();
        $q = $injector.get("$q");
    }));

    // Load the required managers.
    var PodsManager, UsersManager, GeneralManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        PodsManager = $injector.get("PodsManager");
        UsersManager = $injector.get("UsersManager");
        GeneralManager = $injector.get("GeneralManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
    }));

    // Mock the websocket connection to the region
    var RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        RegionConnection = $injector.get("RegionConnection");
        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

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
        var controller = $controller("PodsListController", {
            $scope: $scope,
            $rootScope: $rootScope,
            PodsManager: PodsManager,
            UsersManager: UsersManager,
            ManagerHelperService: ManagerHelperService
        });

        return controller;
    }

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

    it("sets title and page on $rootScope", function() {
        var controller = makeController();
        expect($rootScope.title).toBe("Pods");
        expect($rootScope.page).toBe("pods");
    });

    it("sets initial values on $scope", function() {
        // tab-independent variables.
        var controller = makeController();
        expect($scope.pods).toBe(PodsManager.getItems());
        expect($scope.loading).toBe(true);
        expect($scope.filteredItems).toEqual([]);
        expect($scope.selectedItems).toBe(PodsManager.getSelectedItems());
        expect($scope.predicate).toBe('name');
        expect($scope.allViewableChecked).toBe(false);
        expect($scope.action.option).toBeNull();
        expect($scope.add.open).toBe(false);
        expect($scope.powerTypes).toBe(GeneralManager.getData('power_types'));
    });

    it("calls loadManagers with PodsManager, UsersManager, GeneralManager",
        function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                $scope, [PodsManager, UsersManager, GeneralManager]);
        });

    it("sets loading to false with loadManagers resolves", function() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $rootScope.$digest();
        expect($scope.loading).toBe(false);
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

    describe("toggleChecked", function() {

        var controller, pod;
        beforeEach(function() {
            controller = makeController();
            pod = makePod();
            $scope.filteredItems = $scope.pods;
        });

        it("selects object", function() {
            $scope.toggleChecked(pod);
            expect(pod.$selected).toBe(true);
        });

        it("deselects object", function() {
            PodsManager.selectItem(pod.id);
            $scope.toggleChecked(pod);
            expect(pod.$selected).toBe(false);
        });

        it("sets allViewableChecked to true when all objects selected",
            function() {
                $scope.toggleChecked(pod);
                expect($scope.allViewableChecked).toBe(true);
        });

        it(
            "sets allViewableChecked to false when not all objects " +
            "selected",
            function() {
                var pod2 = makePod();
                $scope.toggleChecked(pod);
                expect($scope.allViewableChecked).toBe(false);
        });

        it("sets allViewableChecked to false when selected and " +
            "deselected",
            function() {
                $scope.toggleChecked(pod);
                $scope.toggleChecked(pod);
                expect($scope.allViewableChecked).toBe(false);
        });

        it("clears action option when none selected", function() {
            $scope.action.option = {};
            $scope.toggleChecked(pod);
            $scope.toggleChecked(pod);
            expect($scope.action.option).toBeNull();
        });
    });

    describe("toggleCheckAll", function() {

        var controller, pod1, pods2;
        beforeEach(function() {
            controller = makeController();
            pod1 = makePod();
            pod2 = makePod();
            $scope.filteredItems = $scope.pods;
        });

        it("selects all objects", function() {
            $scope.toggleCheckAll();
            expect(pod1.$selected).toBe(true);
            expect(pod2.$selected).toBe(true);
        });

        it("deselects all objects", function() {
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect(pod1.$selected).toBe(false);
            expect(pod2.$selected).toBe(false);
        });

        it("clears action option when none selected", function() {
            $scope.action.option = {};
            $scope.toggleCheckAll();
            $scope.toggleCheckAll();
            expect($scope.action.option).toBeNull();
        });
    });

    describe("sortTable", function() {

        it("sets predicate", function() {
            var controller = makeController();
            var predicate = makeName('predicate');
            $scope.sortTable(predicate);
            expect($scope.predicate).toBe(predicate);
        });

        it("reverses reverse", function() {
            var controller = makeController();
            $scope.reverse = true;
            $scope.sortTable(makeName('predicate'));
            expect($scope.reverse).toBe(false);
        });
    });

    describe("actionCancel", function() {

        it("sets actionOption to null", function() {
            var controller = makeController();
            $scope.action.option = {};
            $scope.actionCancel();
            expect($scope.action.option).toBeNull();
        });

        it("resets actionProgress", function() {
            var controller = makeController();
            $scope.action.progress.total = makeInteger(1, 10);
            $scope.action.progress.completed =
                makeInteger(1, 10);
            $scope.action.progress.errors =
                makeInteger(1, 10);
            $scope.actionCancel();
            expect($scope.action.progress.total).toBe(0);
            expect($scope.action.progress.completed).toBe(0);
            expect($scope.action.progress.errors).toBe(0);
        });
    });

    describe("actionGo", function() {

        it("sets action.progress.total to the number of selectedItems",
            function() {
                var controller = makeController();
                var pod = makePod();
                $scope.action.option = { name: "refresh" };
                $scope.action.selectedItems = [
                    makePod(),
                    makePod(),
                    makePod()
                    ];
                $scope.actionGo();
                expect($scope.action.progress.total).toBe(
                    $scope.selectedItems.length);
            });

        it("calls operation for selected action", function() {
            var controller = makeController();
            var pod = makePod();
            var spy = spyOn(
                PodsManager,
                "refresh").and.returnValue($q.defer().promise);
            $scope.action.option = { name: "refresh", operation: spy };
            $scope.selectedItems = [pod];
            $scope.actionGo();
            expect(spy).toHaveBeenCalledWith(pod);
        });

        it("calls unselectItem after failed action", function() {
            var controller = makeController();
            var pod = makePod();
            pod.action_failed = false;
            spyOn(
                $scope, 'hasActionsFailed').and.returnValue(true);
            var defer = $q.defer();
            var refresh = jasmine.createSpy(
                'refresh').and.returnValue(defer.promise);
            var spy = spyOn(PodsManager, "unselectItem");
            $scope.action.option = {
                name: "refresh", operation: refresh };
            $scope.selectedItems = [pod];
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect(spy).toHaveBeenCalled();
        });

        it("keeps items selected after success", function() {
            var controller = makeController();
            var pod = makePod();
            spyOn(
                $scope, 'hasActionsFailed').and.returnValue(false);
            spyOn(
                $scope, 'hasActionsInProgress').and.returnValue(false);
            var defer = $q.defer();
            var refresh = jasmine.createSpy(
                'refresh').and.returnValue(defer.promise);
            var spy = spyOn(PodsManager, "unselectItem");
            $scope.action.option = { name: "refresh", operation: refresh };
            $scope.selectedItems = [pod];
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect($scope.selectedItems).toEqual([pod]);
        });

        it("increments action.progress.completed after action complete",
            function() {
                var controller = makeController();
                var pod = makePod();
                var defer = $q.defer();
                var refresh = jasmine.createSpy(
                    'refresh').and.returnValue(defer.promise);
                spyOn(
                    $scope, 'hasActionsFailed').and.returnValue(true);
                $scope.action.option = { name: "start", operation: refresh };
                $scope.selectedItems = [pod];
                $scope.actionGo();
                defer.resolve();
                $scope.$digest();
                expect($scope.action.progress.completed).toBe(1);
            });

        it("clears action option when complete", function() {
            var controller = makeController();
            var pod = makePod();
            var defer = $q.defer();
            var refresh = jasmine.createSpy(
                'refresh').and.returnValue(defer.promise);
            spyOn(
                $scope, 'hasActionsFailed').and.returnValue(true);
            spyOn(
                $scope, 'hasActionsInProgress').and.returnValue(false);
            PodsManager._items.push(pod);
            PodsManager._selectedItems.push(pod);
            $scope.action.option = { name: "refresh", operation: refresh };
            $scope.actionGo();
            defer.resolve();
            $scope.$digest();
            expect($scope.action.option).toBeNull();
        });

        it("increments action.progress.errors after action error",
            function() {
                var controller = makeController();
                var pod = makePod();
                var defer = $q.defer();
                var refresh = jasmine.createSpy(
                    'refresh').and.returnValue(defer.promise);
                $scope.action.option = { name: "refresh", operation: refresh };
                $scope.selectedItems = [pod];
                $scope.actionGo();
                defer.reject(makeName("error"));
                $scope.$digest();
                expect(
                    $scope.action.progress.errors).toBe(1);
            });

        it("adds error to action.progress.errors on action error",
            function() {
                var controller = makeController();
                var pod = makePod();
                var defer = $q.defer();
                var refresh = jasmine.createSpy(
                    'refresh').and.returnValue(defer.promise);
                $scope.action.option = { name: "refresh", operation: refresh };
                $scope.selectedItems = [pod];
                $scope.actionGo();
                var error = makeName("error");
                defer.reject(error);
                $scope.$digest();
                expect(pod.action_error).toBe(error);
                expect(pod.action_failed).toBe(true);
            });
    });

    describe("hasActionsInProgress", function() {

        it("returns false if action.progress.total not > 0", function() {
            var controller = makeController();
            $scope.action.progress.total = 0;
            expect($scope.hasActionsInProgress()).toBe(false);
        });

        it("returns true if action.progress total != completed",
            function() {
                var controller = makeController();
                $scope.action.progress.total = 1;
                $scope.action.progress.completed = 0;
                expect($scope.hasActionsInProgress()).toBe(true);
            });

        it("returns false if actionProgress total == completed",
            function() {
                var controller = makeController();
                $scope.action.progress.total = 1;
                $scope.action.progress.completed = 1;
                expect($scope.hasActionsInProgress()).toBe(false);
            });
    });

    describe("hasActionsFailed", function() {

        it("returns false if no errors", function() {
            var controller = makeController();
            $scope.action.progress.errors = 0;
            expect($scope.hasActionsFailed()).toBe(false);
        });

        it("returns true if errors", function() {
            var controller = makeController();
            $scope.action.progress.errors = 1;
            expect($scope.hasActionsFailed()).toBe(true);
        });
    });

    describe("addPod", function() {

        it("sets add.open to true", function() {
            var controller = makeController();
            $scope.addPod();
            expect($scope.add.open).toBe(true);
        });
    });

    describe("cancelAddPod", function() {

        it("set add.open to false and clears add.obj", function() {
            var controller = makeController();
            var obj = {};
            $scope.add.obj = obj;
            $scope.add.open = true;
            $scope.cancelAddPod();
            expect($scope.add.open).toBe(false);
            expect($scope.add.obj).toEqual({});
            expect($scope.add.obj).not.toBe(obj);
        });
    });

    describe("getPowerTypeTitle", function() {

        it("returns power_type description", function() {
            var controller = makeController();
            $scope.powerTypes = [
                {
                    name: 'power_type',
                    description: 'Power type'
                }
            ];
            expect($scope.getPowerTypeTitle('power_type')).toBe('Power type');
        });

        it("returns power_type passed in", function() {
            var controller = makeController();
            $scope.powerTypes = [];
            expect($scope.getPowerTypeTitle('power_type')).toBe('power_type');
        });
    });
});
