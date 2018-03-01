/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
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
    var PodsManager, UsersManager, GeneralManager, DomainsManager;
    var ZonesManager, ManagerHelperService, ErrorService;
    beforeEach(inject(function($injector) {
        PodsManager = $injector.get("PodsManager");
        UsersManager = $injector.get("UsersManager");
        GeneralManager = $injector.get("GeneralManager");
        DomainsManager = $injector.get("DomainsManager");
        ZonesManager = $injector.get("ZonesManager");
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
            $selected: false,
            capabilities: []
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
            DomainsManager: DomainsManager,
            ZonesManager: ZonesManager,
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
        expect($scope.compose).toEqual({
          action: {
            name: 'compose',
            title: 'Compose',
            sentence: 'compose'
          },
          obj: {
            storage: [{
              type: 'local',
              size: 8,
              tags: [],
              boot: true
            }]
          }
        });
        expect($scope.power_types).toBe(GeneralManager.getData('power_types'));
        expect($scope.domains).toBe(DomainsManager.getItems());
        expect($scope.zones).toBe(ZonesManager.getItems());
        expect($scope.editing).toBe(false);
    });

    it("calls loadManagers with PodsManager, UsersManager, GeneralManager, \
        DomainsManager, ZonesManager", function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                $scope,
                [
                    PodsManager,
                    GeneralManager,
                    UsersManager,
                    DomainsManager,
                    ZonesManager
                ]);
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

    describe("isRackControllerConnected", function() {
        it("returns false no power_types", function() {
            var controller = makeController();
            $scope.power_types = [];
            expect($scope.isRackControllerConnected()).toBe(false);
        });

        it("returns true if power_types", function() {
            var controller = makeController();
            $scope.power_types = [{}];
            expect($scope.isRackControllerConnected()).toBe(true);
        });
    });

    describe("canEdit", function() {
        it("returns false if not super user", function() {
            var controller = makeController();
            spyOn($scope, "isSuperUser").and.returnValue(false);
            spyOn(
                $scope,
                "isRackControllerConnected").and.returnValue(true);
            expect($scope.canEdit()).toBe(false);
        });

        it("returns false if rack disconnected", function() {
            var controller = makeController();
            spyOn(
                $scope,
                "isRackControllerConnected").and.returnValue(false);
            expect($scope.canEdit()).toBe(false);
        });

        it("returns true if super user, rack connected", function() {
            var controller = makeController();
            spyOn($scope, "isSuperUser").and.returnValue(true);
            spyOn(
                $scope,
                "isRackControllerConnected").and.returnValue(true);
            expect($scope.canEdit()).toBe(true);
        });
    });

    describe("editPodConfiguration", function() {
        it("sets editing to true if can edit",
           function() {
            var controller = makeController();
            spyOn($scope, "canEdit").and.returnValue(true);
            $scope.editing = false;
            $scope.editPodConfiguration();
            expect($scope.editing).toBe(true);
        });

        it("doesnt set editing to true if cannot",
           function() {
            var controller = makeController();
            spyOn($scope, "canEdit").and.returnValue(false);
            $scope.editing = false;
            $scope.editPodConfiguration();
            expect($scope.editing).toBe(false);
        });
    });

    describe("exitEditPodConfiguration", function() {
        it("sets editing to false on exiting pod configuration",
           function() {
            var controller = makeController();
            $scope.editing = true;
            $scope.exitEditPodConfiguration();
            expect($scope.editing).toBe(false);
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

    describe("canCompose", function() {

        it("returns false when no pod", function() {
            var controller = makeController();
            expect($scope.canCompose()).toBe(false);
        });

        it("returns false when not users", function() {
            var controller = makeControllerResolveSetActiveItem();
            spyOn($scope, 'isSuperUser').and.returnValue(false);
            expect($scope.canCompose()).toBe(false);
        });

        it("returns false when not composable", function() {
            var controller = makeControllerResolveSetActiveItem();
            spyOn($scope, 'isSuperUser').and.returnValue(true);
            expect($scope.canCompose()).toBe(false);
        });

        it("returns true when composable", function() {
            var controller = makeControllerResolveSetActiveItem();
            spyOn($scope, 'isSuperUser').and.returnValue(true);
            $scope.pod.capabilities.push('composable');
            expect($scope.canCompose()).toBe(true);
        });
    });

    describe("composeMachine", function() {

        it("sets action.options to compose.action", function() {
            var controller = makeController();
            $scope.composeMachine();
            expect($scope.action.option).toBe($scope.compose.action);
        });
    });

    describe("composePreProcess", function() {

        it("sets id to pod id", function() {
            var controller = makeControllerResolveSetActiveItem();
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: '0:8(local)'
            });
        });

        it("sets storage based on compose.obj.storage", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.compose.obj.storage = [
              {
                type: 'iscsi',
                size: 20,
                tags: [{
                    text: 'one'
                }, {
                    text: 'two'
                }],
                boot: false
              },
              {
                type: 'local',
                size: 50,
                tags: [{
                  text: 'happy'
                }, {
                  text: 'days'
                }],
                boot: true
              },
              {
                type: 'local',
                size: 60,
                tags: [{
                  text: 'other'
                }],
                boot: false
              }
            ];
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: (
                '0:50(local,happy,days),' +
                '1:20(iscsi,one,two),2:60(local,other)')
            });
        });
    });

    describe("cancelCompose", function() {

        it("resets obj and action.option", function() {
            var controller = makeControllerResolveSetActiveItem();
            var otherObj = {};
            $scope.compose.obj = otherObj;
            $scope.action.option = {};
            $scope.cancelCompose();
            expect($scope.compose.obj).not.toBe(otherObj);
            expect($scope.compose.obj).toEqual({
              storage: [{
                type: 'local',
                size: 8,
                tags: [],
                boot: true
              }]
            });
            expect($scope.action.option).toBeNull();
        });
    });

    describe("composeAddStorage", function() {

        it("adds a new local storage item", function() {
            var controller = makeControllerResolveSetActiveItem();
            expect($scope.compose.obj.storage.length).toBe(1);
            $scope.composeAddStorage();
            expect($scope.compose.obj.storage.length).toBe(2);
            expect($scope.compose.obj.storage[1]).toEqual({
              type: 'local',
              size: 8,
              tags: [],
              boot: false
            });
        });

        it("adds a new iscsi storage item", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.capabilities.push('iscsi_storage');
            expect($scope.compose.obj.storage.length).toBe(1);
            $scope.composeAddStorage();
            expect($scope.compose.obj.storage.length).toBe(2);
            expect($scope.compose.obj.storage[1]).toEqual({
              type: 'iscsi',
              size: 8,
              tags: [],
              boot: false
            });
        });
    });

    describe("composeSetBootDisk", function() {

        it("sets a new boot disk", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.composeAddStorage();
            $scope.composeAddStorage();
            $scope.composeAddStorage();
            var newBoot = $scope.compose.obj.storage[3];
            $scope.composeSetBootDisk(newBoot);
            expect($scope.compose.obj.storage[0].boot).toBe(false);
            expect(newBoot.boot).toBe(true);
        });
    });

    describe("composeRemoveDisk", function() {

        it("removes disk from storage", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.composeAddStorage();
            $scope.composeAddStorage();
            $scope.composeAddStorage();
            var deleteStorage = $scope.compose.obj.storage[3];
            $scope.composeRemoveDisk(deleteStorage);
            expect($scope.compose.obj.storage.indexOf(deleteStorage)).toBe(-1);
        });
    });
});
