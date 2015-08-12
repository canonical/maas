/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for AddHardwareController.
 */

describe("AddHardwareController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $timeout, $http, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $timeout = $injector.get("$timeout");
        $http = $injector.get("$http");
        $q = $injector.get("$q");
    }));

    // Load the ClustersManager, ZonesManager, NodesManager, RegionConnection,
    // and mock the websocket connection.
    var ClustersManager, ZonesManager, NodesManager, GeneralManager;
    var RegionConnection, ManagerHelperService, webSocket;
    beforeEach(inject(function($injector) {
        ClustersManager = $injector.get("ClustersManager");
        ZonesManager = $injector.get("ZonesManager");
        NodesManager = $injector.get("NodesManager");
        GeneralManager = $injector.get("GeneralManager");
        RegionConnection = $injector.get("RegionConnection");
        ManagerHelperService = $injector.get("ManagerHelperService");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Create the parent scope and the scope for the controller.
    var parentScope, $scope;
    beforeEach(function() {
        parentScope = $rootScope.$new();
        parentScope.addHardwareScope = null;
        $scope = parentScope.$new();
    });

    // Makes the AddHardwareController
    function makeController(loadManagersDefer, loadManagerDefer) {
        var loadManagers = spyOn(ManagerHelperService, "loadManagers");
        if(angular.isObject(loadManagersDefer)) {
            loadManagers.and.returnValue(loadManagersDefer.promise);
        } else {
            loadManagers.and.returnValue($q.defer().promise);
        }

        var loadManager = spyOn(ManagerHelperService, "loadManager");
        if(angular.isObject(loadManagerDefer)) {
            loadManager.and.returnValue(loadManagerDefer.promise);
        } else {
            loadManager.and.returnValue($q.defer().promise);
        }

        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        return $controller("AddHardwareController", {
            $scope: $scope,
            $timeout: $timeout,
            $http: $http,
            ClustersManager: ClustersManager,
            ZonesManager: ZonesManager,
            NodesManager: NodesManager,
            GeneralManager: GeneralManager,
            RegionConnection: RegionConnection,
            ManagerHelperService: ManagerHelperService
        });
    }

    // Makes the AddHardwareController with the $scope.machine already
    // initialized.
    function makeControllerWithMachine() {
        var defer = $q.defer();
        var controller = makeController(defer);
        defer.resolve();
        $rootScope.$digest();
        return controller;
    }

    it("sets addHardwareScope on $scope.$parent", function() {
        var controller = makeController();
        expect(parentScope.addHardwareScope).toBe($scope);
    });

    it("sets initial values on $scope", function() {
        var controller = makeController();
        expect($scope.viewable).toBe(false);
        expect($scope.clusters).toBe(ClustersManager.getItems());
        expect($scope.zones).toBe(ZonesManager.getItems());
        expect($scope.architectures).toEqual([]);
        expect($scope.hwe_kernels).toEqual([]);
        expect($scope.error).toBeNull();
        expect($scope.machine).toBeNull();
        expect($scope.chassis).toBeNull();
    });

    it("calls loadManagers with ClustersManager and ZonesManager", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManagers).toHaveBeenCalledWith(
            [ClustersManager, ZonesManager]);
    });

    it("calls loadManager with GeneralManager", function() {
        var controller = makeController();
        expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
            GeneralManager);
    });

    it("intializes machine once ClustersManager and ZonesManager loaded",
        function() {
            var defer = $q.defer();
            var controller = makeController(defer);

            defer.resolve();
            $scope.$digest();
            expect($scope.machine).not.toBeNull();
        });

    it("intializes chassis once ClustersManager and ZonesManager loaded",
        function() {
            var defer = $q.defer();
            var controller = makeController(defer);

            defer.resolve();
            $scope.$digest();
            expect($scope.chassis).not.toBeNull();
        });

    it("initializes machine architecture with first arch", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        $scope.architectures = [arch];
        $scope.machine = {
            architecture: ''
        };

        defer.resolve();
        $scope.$digest();
        expect($scope.machine.architecture).toEqual(arch);
    });

    it("initializes machine architecture with amd64 arch", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        $scope.architectures = [arch, "amd64/generic"];
        $scope.machine = {
            architecture: ''
        };

        defer.resolve();
        $scope.$digest();
        expect($scope.machine.architecture).toEqual("amd64/generic");
    });

    it("doesnt initializes machine architecture if set", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        var newArch = makeName("arch");
        $scope.architectures = [newArch];
        $scope.machine = {
            architecture: arch
        };

        defer.resolve();
        $scope.$digest();
        expect($scope.machine.architecture).toEqual(arch);
    });

    it("initializes machine min_hwe_kernel with hwe-t", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        var min_hwe_kernel = "hwe-t";
        $scope.architectures = [arch];
        $scope.machine = {
            architecture: '',
            min_hwe_kernel: 'hwe-t'
        };

        defer.resolve();
        $scope.$digest();
        expect($scope.machine.min_hwe_kernel).toEqual("hwe-t");
    });

    it("calls stopPolling when scope destroyed", function() {
        var controller = makeController();
        spyOn(GeneralManager, "stopPolling");
        $scope.$destroy();
        expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
            "architectures");
        expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
            "hwe_kernels");
    });

    describe("show", function() {

        it("sets viewable to true", function() {
            var controller = makeController();
            $scope.show();
            expect($scope.viewable).toBe(true);
        });

        it("calls startPolling for architectures", function() {
            var controller = makeController();
            spyOn(GeneralManager, "startPolling");
            $scope.show();
            expect(GeneralManager.startPolling).toHaveBeenCalledWith(
                "architectures");
        });

        it("calls startPolling for hwe_kernels", function() {
            var controller = makeController();
            spyOn(GeneralManager, "startPolling");
            $scope.show();
            expect(GeneralManager.startPolling).toHaveBeenCalledWith(
                "hwe_kernels");
        });
    });

    describe("hide", function() {

        it("sets viewable to false", function() {
            var controller = makeController();
            $scope.viewable = true;
            $scope.hide();
            expect($scope.viewable).toBe(false);
        });

        it("calls stopPolling for architectures", function() {
            var controller = makeController();
            spyOn(GeneralManager, "stopPolling");
            $scope.hide();
            expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
                "architectures");
        });

        it("calls stopPolling for hwe_kernels", function() {
            var controller = makeController();
            spyOn(GeneralManager, "stopPolling");
            $scope.hide();
            expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
                "hwe_kernels");
        });

        it("emits addHardwareHidden event", function(done) {
            var controller = makeController();
            $scope.$on("addHardwareHidden", function() {
                done();
            });
            $scope.hide();
        });
    });

    describe("addMac", function() {

        it("adds mac address object to machine", function() {
            var controller = makeControllerWithMachine();
            $scope.addMac();
            expect($scope.machine.macs.length).toBe(2);
        });
    });

    describe("removeMac", function() {

        it("removes mac address object from machine", function() {
            var controller = makeControllerWithMachine();
            $scope.addMac();
            var mac = $scope.machine.macs[1];
            $scope.removeMac(mac);
            expect($scope.machine.macs.length).toBe(1);
        });

        it("ignores second remove if mac object removed again", function() {
            var controller = makeControllerWithMachine();
            $scope.addMac();
            var mac = $scope.machine.macs[1];
            $scope.removeMac(mac);
            $scope.removeMac(mac);
            expect($scope.machine.macs.length).toBe(1);
        });
    });

    describe("invalidName", function() {

        it("return false if machine name empty", function() {
            var controller = makeControllerWithMachine();
            expect($scope.invalidName($scope.machine)).toBe(false);
        });

        it("return false if machine name valid", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.name = "abc";
            expect($scope.invalidName($scope.machine)).toBe(false);
        });

        it("return true if machine name invalid", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.name = "ab_c.local";
            expect($scope.invalidName($scope.machine)).toBe(true);
        });
    });

    describe("validateMac", function() {

        it("sets error to false if blank", function() {
            var controller = makeController();
            var mac = {
                mac: '',
                error: true
            };
            $scope.validateMac(mac);
            expect(mac.error).toBe(false);
        });

        it("sets error to true if invalid", function() {
            var controller = makeController();
            var mac = {
                mac: '00:11:22',
                error: false
            };
            $scope.validateMac(mac);
            expect(mac.error).toBe(true);
        });

        it("sets error to false if valid", function() {
            var controller = makeController();
            var mac = {
                mac: '00:11:22:33:44:55',
                error: true
            };
            $scope.validateMac(mac);
            expect(mac.error).toBe(false);
        });
    });

    describe("machineHasError", function() {

        it("returns true if machine is null", function() {
            var controller = makeControllerWithMachine();
            $scope.machine = null;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if cluster is null", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = null;
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if zone is null", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = null;
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if architecture is empty", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = '';
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if power.type is null", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = null;
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if machine.name invalid", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.name = "ab_c.local";
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if mac[0] is empty", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if mac[0] is in error", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44';
            $scope.machine.macs[0].error = true;
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns true if mac[1] is in error", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            $scope.machine.macs.push({
                mac: '00:11:22:33:55',
                error: true
            });
            expect($scope.machineHasError()).toBe(true);
        });

        it("returns false if all is correct", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            expect($scope.machineHasError()).toBe(false);
        });

        it("returns false if all is correct and mac[1] is blank", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.cluster = {};
            $scope.machine.zone = {};
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {};
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            $scope.machine.macs.push({
                mac: '',
                error: false
            });
            expect($scope.machineHasError()).toBe(false);
        });
    });

    describe("chassisHasErrors", function() {

        it("returns true if chassis is null", function() {
            var controller = makeController();
            $scope.chassis = null;
            expect($scope.chassisHasErrors()).toBe(true);
        });

        it("returns true if cluster is null", function() {
            var controller = makeController();
            $scope.chassis = {
                cluster: null,
                power: {
                    type: {},
                    parameters: {}
                }
            };
            expect($scope.chassisHasErrors()).toBe(true);
        });

        it("returns true if power.type is null", function() {
            var controller = makeController();
            $scope.chassis = {
                cluster: {},
                power: {
                    type: null,
                    parameters: {}
                }
            };
            expect($scope.chassisHasErrors()).toBe(true);
        });

        it("returns true if power.parameters is invalid", function() {
            var controller = makeController();
            $scope.chassis = {
                cluster: {},
                power: {
                    type: {
                        fields: [
                            {
                                name: "test",
                                required: true
                            }
                        ]
                    },
                    parameters: {
                        test: ""
                    }
                }
            };
            expect($scope.chassisHasErrors()).toBe(true);
        });

        it("returns false if all valid", function() {
            var controller = makeController();
            $scope.chassis = {
                cluster: {},
                power: {
                    type: {
                        fields: [
                            {
                                name: "test",
                                required: true
                            }
                        ]
                    },
                    parameters: {
                        test: "data"
                    }
                }
            };
            expect($scope.chassisHasErrors()).toBe(false);
        });
    });

    describe("cancel", function() {

        it("clears error", function() {
            var controller = makeControllerWithMachine();
            $scope.error = makeName("error");
            $scope.cancel();
            expect($scope.error).toBeNull();
        });

        it("clears machine and adds a new one", function() {
            var controller = makeControllerWithMachine();
            $scope.machine.name = makeName("name");
            $scope.cancel();
            expect($scope.machine.name).toBe("");
        });

        it("clears chassis and adds a new one", function() {
            var controller = makeControllerWithMachine();
            $scope.chassis.power.type = makeName("type");
            $scope.cancel();
            expect($scope.chassis.power.type).toBeNull();
        });

        it("calls hide", function() {
            var controller = makeControllerWithMachine();
            spyOn($scope, "hide");
            $scope.cancel();
            expect($scope.hide).toHaveBeenCalled();
        });
    });

    describe("saveMachine", function() {

        // Setup a valid machine before each test.
        beforeEach(function() {
            var controller = makeControllerWithMachine();

            $scope.addMac();
            $scope.machine.name = makeName("name").replace("_", "");
            $scope.machine.cluster = {
                id: 1,
                uuid: makeName("uuid"),
                cluster_name: makeName("cluster_name")
            };
            $scope.machine.zone = {
                id: 1,
                name: makeName("zone")
            };
            $scope.machine.architecture = makeName("arch");
            $scope.machine.power.type = {
                name: "ether_wake"
            };
            $scope.machine.power.parameters = {
                mac_address: "00:11:22:33:44:55"
            };
            $scope.machine.macs[0].mac = '00:11:22:33:44:55';
            $scope.machine.macs[0].error = false;
            $scope.machine.macs[1].mac = '00:11:22:33:44:66';
            $scope.machine.macs[1].error = false;
        });

        it("does nothing if errors", function() {
            var error = makeName("error");
            $scope.error = error;
            // Force the machine to be invalid.
            spyOn($scope, "machineHasError").and.returnValue(true);
            $scope.saveMachine(false);
            expect($scope.error).toBe(error);
        });

        it("clears error", function() {
            $scope.error = makeName("error");
            $scope.saveMachine(false);
            expect($scope.error).toBeNull();
        });

        it("calls NodesManager.create with converted machine", function() {
            spyOn(NodesManager, "create").and.returnValue($q.defer().promise);

            $scope.saveMachine(false);
            expect(NodesManager.create).toHaveBeenCalledWith({
                hostname: $scope.machine.name,
                architecture: $scope.machine.architecture,
                min_hwe_kernel: $scope.machine.min_hwe_kernel,
                pxe_mac: $scope.machine.macs[0].mac,
                extra_macs: [$scope.machine.macs[1].mac],
                power_type: $scope.machine.power.type.name,
                power_parameters: $scope.machine.power.parameters,
                zone: {
                    id: $scope.machine.zone.id,
                    name: $scope.machine.zone.name
                },
                nodegroup: {
                    id: $scope.machine.cluster.id,
                    uuid: $scope.machine.cluster.uuid,
                    cluster_name: $scope.machine.cluster.cluster_name
                }
            });
        });

        it("calls hide once NodesManager.create is resolved", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "create").and.returnValue(defer.promise);
            spyOn($scope, "hide");
            $scope.saveMachine(false);
            defer.resolve();
            $rootScope.$digest();

            expect($scope.hide).toHaveBeenCalled();
        });

        it("resets machine once NodesManager.create is resolved", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "create").and.returnValue(defer.promise);
            $scope.saveMachine(false);
            defer.resolve();
            $rootScope.$digest();

            expect($scope.machine.name).toBe("");
        });

        it("clones machine once NodesManager.create is resolved", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "create").and.returnValue(defer.promise);

            var cluster_name = $scope.machine.cluster.cluster_name;
            $scope.saveMachine(true);
            defer.resolve();
            $rootScope.$digest();

            expect($scope.machine.name).toBe("");
            expect($scope.machine.cluster.cluster_name).toBe(cluster_name);
        });

        it("deosnt call hide if addAnother is true", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "create").and.returnValue(defer.promise);
            spyOn($scope, "hide");

            $scope.saveMachine(true);
            defer.resolve();
            $rootScope.$digest();

            expect($scope.hide).not.toHaveBeenCalled();
        });

        it("sets error when NodesManager.create is rejected", function() {
            var defer = $q.defer();
            spyOn(NodesManager, "create").and.returnValue(defer.promise);
            spyOn($scope, "hide");

            var error = makeName("error");
            $scope.saveMachine(false);
            defer.reject(error);
            $rootScope.$digest();

            expect($scope.error).toBe(error);
            expect($scope.hide).not.toHaveBeenCalled();
        });
    });

    describe("saveChassis", function() {

        // Setup a valid chassis before each test.
        var httpDefer;
        beforeEach(function() {
            httpDefer = $q.defer();

            // Mock $http.
            $http = jasmine.createSpy("$http");
            $http.and.returnValue(httpDefer.promise);

            // Create the controller and the valid chassis.
            var controller = makeController();
            $scope.chassis = {
                cluster: {
                    uuid: makeName("uuid")
                },
                power: {
                    type: {
                        name: makeName("model"),
                        fields: [
                            {
                                name: "one",
                                required: true
                            },
                            {
                                name: "one",
                                required: true
                            }
                        ]
                    },
                    parameters: {
                        "one": makeName("one"),
                        "two": makeName("two")
                    }
                }
            };
        });

        it("does nothing if errors", function() {
            var error = makeName("error");
            $scope.error = error;
            spyOn($scope, "chassisHasErrors").and.returnValue(true);
            $scope.saveChassis(false);
            expect($scope.error).toBe(error);
        });

        it("calls $http with correct parameters", function() {
            $scope.saveChassis(false);

            var parameters = $scope.chassis.power.parameters;
            parameters.model = $scope.chassis.power.type.name;
            expect($http).toHaveBeenCalledWith({
                method: 'POST',
                url: 'api/1.0/nodegroups/' + $scope.chassis.cluster.uuid +
                    '/?op=probe_and_enlist_hardware',
                data: $.param(parameters),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            });
        });

        it("creates new chassis when $http resolves", function() {
            $scope.saveChassis(false);
            httpDefer.resolve();
            $rootScope.$digest();

            expect($scope.chassis.power.type).toBeNull();
        });

        it("calls hide if addAnother false when $http resolves", function() {
            spyOn($scope, "hide");
            $scope.saveChassis(false);
            httpDefer.resolve();
            $rootScope.$digest();

            expect($scope.hide).toHaveBeenCalled();
        });

        it("doesnt call hide if addAnother true when $http resolves",
            function() {
                spyOn($scope, "hide");
                $scope.saveChassis(true);
                httpDefer.resolve();
                $rootScope.$digest();

                expect($scope.hide).not.toHaveBeenCalled();
            });

        it("sets error when $http rejects", function() {
            $scope.saveChassis(false);
            var error = makeName("error");
            httpDefer.reject(error);
            $rootScope.$digest();

            expect($scope.error).toBe(error);
        });
    });
});
