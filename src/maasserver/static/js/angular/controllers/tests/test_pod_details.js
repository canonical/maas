/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for PodDetailsController.
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
    var SubnetsManager, VLANsManager, FabricsManager, SpacesManager;
    var ResourcePoolsManager;
    beforeEach(inject(function($injector) {
        PodsManager = $injector.get("PodsManager");
        UsersManager = $injector.get("UsersManager");
        GeneralManager = $injector.get("GeneralManager");
        DomainsManager = $injector.get("DomainsManager");
        ZonesManager = $injector.get("ZonesManager");
        MachinesManager = $injector.get("MachinesManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ErrorService = $injector.get("ErrorService");
        SubnetsManager = $injector.get("SubnetsManager");
        VLANsManager = $injector.get("VLANsManager");
        FabricsManager = $injector.get("FabricsManager");
        SpacesManager = $injector.get("SpacesManager");
        ResourcePoolsManager = $injector.get("ResourcePoolsManager");
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
            default_pool: 0,
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
        domain = {id: 0};
        DomainsManager._items.push(domain);
        zone = {id: 0};
        ZonesManager._items.push(domain);
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
            MachinesManager: MachinesManager,
            ManagerHelperService: ManagerHelperService,
            ErrorService: ErrorService,
            SubnetsManager: SubnetsManager,
            VLANsManager: VLANsManager,
            FabricsManager: FabricsManager,
            SpacesManager: SpacesManager,
            ResourcePoolsManager: ResourcePoolsManager
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
              pool: {},
              boot: true
            }],
            interfaces: [{
              name: 'default'
            }],
            requests: []
          }
        });
        expect($scope.power_types).toBe(GeneralManager.getData('power_types'));
        expect($scope.domains).toBe(DomainsManager.getItems());
        expect($scope.zones).toBe(ZonesManager.getItems());
        expect($scope.pools).toBe(ResourcePoolsManager.getItems());
        expect($scope.editing).toBe(false);
    });

    it("calls loadManagers with PodsManager, UsersManager, GeneralManager, \
        DomainsManager, ZonesManager, SubnetsManager, VLANsManager, \
        FabricsManager, SpacesManager, MachinesManager", function() {
            var controller = makeController();
            expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
                $scope,
                [
                    PodsManager,
                    GeneralManager,
                    UsersManager,
                    DomainsManager,
                    ZonesManager,
                    MachinesManager,
                    ResourcePoolsManager,
                    SubnetsManager,
                    VLANsManager,
                    FabricsManager,
                    SpacesManager
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

    describe("editName", function() {

        it("doesnt set editing true",
           function() {
            var controller = makeController();
            spyOn($scope, "canEdit").and.returnValue(false);
            $scope.name.editing = false;
            $scope.editName();
            expect($scope.name.editing).toBe(false);
        });

        it("sets editing to true",
           function() {
            var controller = makeController();
            $scope.pod = pod;
            spyOn($scope, "canEdit").and.returnValue(true);
            $scope.name.editing = false;
            $scope.editName();
            expect($scope.name.editing).toBe(true);
        });

        it("sets name.value to pod name", function() {
            var controller = makeController();
            $scope.pod = pod;
            spyOn($scope, "canEdit").and.returnValue(true);
            $scope.editName();
            expect($scope.name.value).toBe(pod.name);
        });

        it("doesnt reset name.value on multiple calls", function() {
            var controller = makeController();
            $scope.pod = pod;
            spyOn($scope, "canEdit").and.returnValue(true);
            $scope.editName();
            var updatedName = makeName("name");
            $scope.name.value = updatedName;
            $scope.editName();
            expect($scope.name.value).toBe(updatedName);
        });
    });

    describe("editNameInvalid", function() {

        it("returns false if not editing", function() {
            var controller = makeController();
            $scope.name.editing = false;
            $scope.name.value = "abc_invalid.local";
            expect($scope.editNameInvalid()).toBe(false);
        });

        it("returns true for bad values", function() {
            var controller = makeController();
            $scope.name.editing = true;
            var values = [
                {
                    input: "aB0-z",
                    output: false
                },
                {
                    input: "abc_alpha",
                    output: true
                },
                {
                    input: "ab^&c",
                    output: true
                },
                {
                    input: "abc.local",
                    output: true
                }
            ];
            angular.forEach(values, function(value) {
                $scope.name.value = value.input;
                expect($scope.editNameInvalid()).toBe(value.output);
            });
        });
    });

    describe("cancelEditName", function() {

        it("sets editing to false for name section",
           function() {
            var controller = makeController();
            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.cancelEditName();
            expect($scope.name.editing).toBe(false);
        });

        it("sets name.value back to original", function() {
            var controller = makeController();
            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.name.value = makeName("name");
            $scope.cancelEditName();
            expect($scope.name.value).toBe(pod.name);
        });
    });

    describe("saveEditName", function() {

        it("does nothing if value is invalid", function() {
            var controller = makeController();
            $scope.pod = pod;
            spyOn($scope, "editNameInvalid").and.returnValue(true);
            var sentinel = {};
            $scope.name.editing = sentinel;
            $scope.saveEditName();
            expect($scope.name.editing).toBe(sentinel);
        });

        it("sets editing to false", function() {
            var controller = makeController();
            spyOn(PodsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            spyOn($scope, "editNameInvalid").and.returnValue(false);

            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.name.value = makeName("name");
            $scope.saveEditName();

            expect($scope.name.editing).toBe(false);
        });

        it("calls updateItem with copy of pod", function() {
            var controller = makeController();
            spyOn(PodsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            spyOn($scope, "editNameInvalid").and.returnValue(false);

            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.name.value = makeName("name");
            $scope.saveEditName();

            var calledWithPod = PodsManager.updateItem.calls.argsFor(0)[0];
            expect(calledWithPod).not.toBe(pod);
        });

        it("calls updateItem with new name on pod", function() {
            var controller = makeController();
            spyOn(PodsManager, "updateItem").and.returnValue(
                $q.defer().promise);
            spyOn($scope, "editNameInvalid").and.returnValue(false);

            var newName = makeName("name");
            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.name.value = newName;
            $scope.saveEditName();

            var calledWithPod = PodsManager.updateItem.calls.argsFor(0)[0];
            expect(calledWithPod.name).toBe(newName);
        });

        it("calls updateName once updateItem resolves", function() {
            var controller = makeController();
            var defer = $q.defer();
            spyOn(PodsManager, "updateItem").and.returnValue(
                defer.promise);
            spyOn($scope, "editNameInvalid").and.returnValue(false);

            $scope.pod = pod;
            $scope.name.editing = true;
            $scope.name.value = makeName("name");
            $scope.saveEditName();

            defer.resolve(pod);
            $rootScope.$digest();

            // Since updateName is private in the controller, check
            // that the name.value is set to the pod's name.
            expect($scope.name.value).toBe(pod.name);
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

    describe("totalStoragePercentage", function() {
        it("returns the correct percentage", function() {
            var controller = makeController();
            var storage_pool = {
                'used': 40,
                'total': 100
            }
            var storage = 10;
            expect($scope.totalStoragePercentage(
                storage_pool, storage)).toBe(50);
        });

        it("returns the over committed percentage", function() {
            var controller = makeController();
            var storage_pool = {
                'used': 90,
                'total': 100
            }
            var storage = 60;
            expect($scope.totalStoragePercentage(
                storage_pool, storage)).toBe(150);
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

        it("sets action.options to compose.action", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.default_pool = 42;
            $scope.composeMachine();
            $scope.$digest();
            expect($scope.compose.obj.pool).toBe(42);
        });
    });

    describe("composePreProcess", function() {

        it("sets id to pod id", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.type = 'rsd';
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: '0:8(local)',
              interfaces: ''
            });
        });

        it("sets rsd storage based on compose.obj.storage", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.type = 'rsd';
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
                '1:20(iscsi,one,two),2:60(local,other)'),
              interfaces: ''
            });
        });

        it("sets the interface constraint for subnets", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.compose.obj.interfaces = [
              {
                name: 'eth0',
                subnet: {cidr: '172.16.4.0/24'}
              },
              {
                name: 'eth1',
                subnet: {cidr: '192.168.1.0/24'}
              }
            ];
            var expectedInterfaces = [
                'eth0:subnet_cidr=172.16.4.0/24',
                'eth1:subnet_cidr=192.168.1.0/24'
            ].join(';')
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: '0:8()',
              interfaces: expectedInterfaces
            });
        });

        it("sets the interface constraint favouring ip addresses", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.compose.obj.interfaces = [
              {
                name: 'eth0',
                ipaddress: '172.16.4.2',
                subnet: {cidr: '172.16.4.0/24'}
              },
              {
                name: 'eth1',
                ipaddress: '192.168.1.5',
                subnet: {cidr: '192.168.1.0/24'}
              },
              {
                name: 'eth2',
                subnet: {cidr: '192.168.2.0/24'}
              }
            ];
            var expectedInterfaces = [
                'eth0:ip=172.16.4.2',
                'eth1:ip=192.168.1.5',
                'eth2:subnet_cidr=192.168.2.0/24'
            ].join(';')
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: '0:8()',
              interfaces: expectedInterfaces
            });
        });

        it("sets virsh storage based on compose.obj.storage", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.type = 'virsh';
            $scope.compose.obj.storage = [
              {
                size: 20,
                pool: {
                    name: 'pool1'
                },
                tags: [{
                    text: 'one'
                }, {
                    text: 'two'
                }],
                boot: false
              },
              {
                size: 50,
                pool: {
                    name: 'pool2'
                },
                tags: [{
                  text: 'happy'
                }, {
                  text: 'days'
                }],
                boot: true
              },
              {
                size: 60,
                pool: {
                    name: 'pool3'
                },
                tags: [{
                  text: 'other'
                }],
                boot: false
              }
            ];
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: (
                '0:50(pool2,happy,days),' +
                '1:20(pool1,one,two),2:60(pool3,other)'),
              interfaces: ''
            });
        });

        it("sets virsh storage based on compose.obj.storage", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.pod.type = 'virsh';
            $scope.compose.obj.storage = [
              {
                size: 20,
                pool: {
                    name: 'pool1'
                },
                tags: [{
                    text: 'one'
                }, {
                    text: 'two'
                }],
                boot: false
              },
              {
                size: 50,
                pool: {
                    name: 'pool2'
                },
                tags: [{
                  text: 'happy'
                }, {
                  text: 'days'
                }],
                boot: true
              },
              {
                size: 60,
                pool: {
                    name: 'pool3'
                },
                tags: [{
                  text: 'other'
                }],
                boot: false
              }
            ];
            expect($scope.composePreProcess({})).toEqual({
              id: $scope.pod.id,
              storage: (
                '0:50(pool2,happy,days),' +
                '1:20(pool1,one,two),2:60(pool3,other)'),
              interfaces: ''
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
                pool: {},
                boot: true
              }],
              interfaces: [{
                name: 'default'
              }],
              requests: []
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
              pool: {},
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
              pool: {},
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

    describe("composeAddInterface", function() {

        it("adds a new interface item and removes the default", function() {
            var controller = makeControllerResolveSetActiveItem();
            expect($scope.compose.obj.interfaces.length).toBe(1);
            expect($scope.compose.obj.interfaces[0]).toEqual({
                name: 'default'
            });
            $scope.composeAddInterface();
            expect($scope.compose.obj.interfaces.length).toBe(1);
            expect($scope.compose.obj.interfaces[0]).toEqual({
                name: 'eth0'
            });
        });

        it("increments the default interface name", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.composeAddInterface();
            $scope.composeAddInterface();
            expect($scope.compose.obj.interfaces[0]).toEqual({
                name: 'eth0'
            });
            expect($scope.compose.obj.interfaces[1]).toEqual({
                name: 'eth1'
            });
        });
    });

    describe("composeRemoveInterface", function() {

        it("removes interface from interfaces table", function() {
            var controller = makeControllerResolveSetActiveItem();
            $scope.composeAddInterface();
            $scope.composeAddInterface();
            $scope.composeAddInterface();
            var deletedIface = $scope.compose.obj.interfaces[3];
            $scope.composeRemoveInterface(deletedIface);

            expect($scope.compose.obj.interfaces.indexOf(
                deletedIface)).toBe(-1);
        });
    });


});
