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
        expect($scope.machines).toEqual([]);
        expect($scope.currentMachine).toBeNull();
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

    it("intializes first machine once ClustersManager and ZonesManager loaded",
        function() {
            var defer = $q.defer();
            var controller = makeController(defer);

            defer.resolve();
            $scope.$digest();
            expect($scope.machines.length).toBe(1);
        });

    it("intializes chassis once ClustersManager and ZonesManager loaded",
        function() {
            var defer = $q.defer();
            var controller = makeController(defer);

            defer.resolve();
            $scope.$digest();
            expect($scope.chassis).not.toBeNull();
        });

    it("initializes currentMachine architecture with first arch", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        $scope.architectures = [arch];

        var machine = {
            architecture: ''
        };
        $scope.machines.push(machine);
        $scope.currentMachine = machine;

        defer.resolve();
        $scope.$digest();
        expect(machine.architecture).toEqual(arch);
    });

    it("initializes currentMachine architecture with amd64 arch", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        $scope.architectures = [arch, "amd64/generic"];

        var machine = {
            architecture: ''
        };
        $scope.machines.push(machine);
        $scope.currentMachine = machine;

        defer.resolve();
        $scope.$digest();
        expect(machine.architecture).toEqual("amd64/generic");
    });

    it("doesnt initializes currentMachine architecture if set", function() {
        var defer = $q.defer();
        var controller = makeController(null, defer);
        var arch = makeName("arch");
        var newArch = makeName("arch");
        $scope.architectures = [newArch];

        var machine = {
            architecture: arch
        };
        $scope.machines.push(machine);
        $scope.currentMachine = machine;

        defer.resolve();
        $scope.$digest();
        expect(machine.architecture).toEqual(arch);
    });

    it("calls stopPolling when scope destroyed", function() {
        var controller = makeController();
        spyOn(GeneralManager, "stopPolling");
        $scope.$destroy();
        expect(GeneralManager.stopPolling).toHaveBeenCalledWith(
            "architectures");
    });

    describe("show", function() {

        it("sets viewable to true", function() {
            var controller = makeController();
            $scope.show();
            expect($scope.viewable).toBe(true);
        });

        it("updates currentMachine with random hostname", function(done) {
            var controller = makeController();
            $scope.addMachine();
            $scope.currentMachine.name = "";
            var hostname = makeName("hostname");

            // Return the hostname.
            webSocket.returnData.push(makeFakeResponse(hostname));

            $scope.show().then(function() {
                expect($scope.currentMachine.name).toBe(hostname);
                done();
            });
        });

        it("calls startPolling for architectures", function() {
            var controller = makeController();
            spyOn(GeneralManager, "startPolling");
            $scope.show();
            expect(GeneralManager.startPolling).toHaveBeenCalledWith(
                "architectures");
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

        it("emits addHardwareHidden event", function(done) {
            var controller = makeController();
            $scope.$on("addHardwareHidden", function() {
                done();
            });
            $scope.hide();
        });
    });

    describe("addMac", function() {

        it("adds mac address object to currentMachine", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.addMac();
            expect($scope.currentMachine.macs.length).toBe(2);
        });
    });

    describe("addMachine", function() {

        it("adds new machine to list and sets as currentMachine", function() {
            var controller = makeController();
            $scope.addMachine();
            expect($scope.machines).toEqual([$scope.currentMachine]);
        });

        it("sets random hostname on machine", function(done) {
            var controller = makeController();
            var hostname = makeName("hostname");
            webSocket.returnData.push(makeFakeResponse(hostname));
            $scope.addMachine().then(function() {
                expect($scope.currentMachine.name).toBe(hostname);
                done();
            });
        });
    });

    describe("setCurrentMachine", function() {

        it("sets currentMachine", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.addMachine();
            expect($scope.currentMachine).toBe($scope.machines[1]);
            $scope.setCurrentMachine($scope.machines[0]);
            expect($scope.currentMachine).toBe($scope.machines[0]);
        });
    });

    describe("invalidName", function() {

        it("return false if machine name empty", function() {
            var controller = makeController();
            $scope.addMachine();
            expect($scope.invalidName($scope.currentMachine)).toBe(false);
        });

        it("return false if machine name valid", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.currentMachine.name = "abc";
            expect($scope.invalidName($scope.currentMachine)).toBe(false);
        });

        it("return true if machine name invalid", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.currentMachine.name = "ab_c.local";
            expect($scope.invalidName($scope.currentMachine)).toBe(true);
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

        it("returns true if cluster is null", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = null;
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if zone is null", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = null;
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if architecture is empty", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = '';
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if power.type is null", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = null;
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if machine.name invalid", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.name = "ab_c.local";
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if mac[0] is empty", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if mac[0] is in error", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44';
            machine.macs[0].error = true;
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns true if mac[1] is in error", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            machine.macs.push({
                mac: '00:11:22:33:55',
                error: true
            });
            expect($scope.machineHasError(machine)).toBe(true);
        });

        it("returns false if all is correct", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            expect($scope.machineHasError(machine)).toBe(false);
        });

        it("returns false if all is correct and mac[1] is blank", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            machine.cluster = {};
            machine.zone = {};
            machine.architecture = makeName("arch");
            machine.power.type = {};
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            machine.macs.push({
                mac: '',
                error: false
            });
            expect($scope.machineHasError(machine)).toBe(false);
        });
    });

    describe("machinesHaveErrors", function() {

        it("returns true if one machine has error", function() {
            var controller = makeController();

            // 1st machine, no errors.
            $scope.addMachine();
            var machine1 = $scope.currentMachine;
            machine1.cluster = {};
            machine1.zone = {};
            machine1.architecture = makeName("arch");
            machine1.power.type = {};
            machine1.macs[0].mac = '00:11:22:33:44:55';
            machine1.macs[0].error = false;

            // 2nd machine, errors.
            $scope.addMachine();
            var machine2 = $scope.currentMachine;
            machine2.cluster = {};
            machine2.zone = {};
            machine2.architecture = '';
            machine2.power.type = {};
            machine2.macs[0].mac = '00:11:22:33:44:66';
            machine2.macs[0].error = false;

            expect($scope.machinesHaveErrors()).toBe(true);
        });

        it("returns false if no machines have errors", function() {
            var controller = makeController();

            // 1st machine, no errors.
            $scope.addMachine();
            var machine1 = $scope.currentMachine;
            machine1.cluster = {};
            machine1.zone = {};
            machine1.architecture = makeName("arch");
            machine1.power.type = {};
            machine1.macs[0].mac = '00:11:22:33:44:55';
            machine1.macs[0].error = false;

            // 2nd machine, no errors.
            $scope.addMachine();
            var machine2 = $scope.currentMachine;
            machine2.cluster = {};
            machine2.zone = {};
            machine2.architecture = makeName("arch");
            machine2.power.type = {};
            machine2.macs[0].mac = '00:11:22:33:44:66';
            machine2.macs[0].error = false;

            expect($scope.machinesHaveErrors()).toBe(false);
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

    describe("getDisplayMac", function() {

        it("returns 00:00:00:00:00:00 when mac[0] is empty", function() {
            var controller = makeController();
            $scope.addMachine();
            expect($scope.getDisplayMac($scope.currentMachine)).toBe(
                "00:00:00:00:00:00");
        });

        it("returns mac from mac[0]", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.addMac();
            $scope.currentMachine.macs[0].mac = "00:11";
            expect($scope.getDisplayMac($scope.currentMachine)).toBe("00:11");
        });
    });

    describe("getDisplayPower", function() {

        it("returns missing text when power.type is null", function() {
            var controller = makeController();
            $scope.addMachine();
            expect($scope.getDisplayPower($scope.currentMachine)).toBe(
                "Missing power type");
        });

        it("returns power description", function() {
            var controller = makeController();
            $scope.addMachine();
            var description = makeName("description");
            $scope.currentMachine.power.type = {
                description: description
            };
            expect($scope.getDisplayPower($scope.currentMachine)).toBe(
                description);
        });
    });

    describe("actionCancel", function() {

        it("clears machines and adds a new one", function() {
            var controller = makeController();
            $scope.addMachine();
            $scope.addMachine();
            $scope.addMachine();
            $scope.actionCancel();
            expect($scope.machines.length).toBe(1);
            expect($scope.currentMachine).toBe($scope.machines[0]);
        });

        it("calls hide", function() {
            var controller = makeController();
            spyOn($scope, "hide");
            $scope.actionCancel();
            expect($scope.hide).toHaveBeenCalled();
        });
    });

    describe("actionAddMachines", function() {

        it("does nothing if errors", function() {
            var controller = makeController();
            $scope.addMachine();
            var machine = $scope.currentMachine;
            spyOn($scope, "machinesHaveErrors").and.returnValue(true);
            $scope.actionAddMachines();
            expect($scope.currentMachine).toBe(machine);
        });

        it("clears machines and adds a new one", function() {
            var controller = makeController();

            // Valid 1st machine
            $scope.addMachine();
            var machine1 = $scope.currentMachine;
            machine1.cluster = {};
            machine1.zone = {};
            machine1.architecture = makeName("arch");
            machine1.power.type = {};
            machine1.macs[0].mac = '00:11:22:33:44:55';
            machine1.macs[0].error = false;

            // Valid 2nd machine
            $scope.addMachine();
            var machine2 = $scope.currentMachine;
            machine2.cluster = {};
            machine2.zone = {};
            machine2.architecture = makeName("arch");
            machine2.power.type = {};
            machine2.macs[0].mac = '00:11:22:33:44:55';
            machine2.macs[0].error = false;

            $scope.actionAddMachines();
            expect($scope.machines.length).toBe(1);
            expect($scope.currentMachine).toBe($scope.machines[0]);
        });

        it("calls hide", function() {
            var controller = makeController();
            spyOn($scope, "machinesHaveErrors").and.returnValue(false);
            spyOn($scope, "hide");
            $scope.actionAddMachines();
            expect($scope.hide).toHaveBeenCalled();
        });

        it("calls NodesManager.create with converted machine", function() {
            var controller = makeController();

            $scope.addMachine();
            $scope.addMac();
            spyOn($scope, "invalidName").and.returnValue(false);
            var machine = $scope.currentMachine;
            machine.name = makeName("name");
            machine.cluster = {
                id: 1,
                uuid: makeName("uuid"),
                cluster_name: makeName("cluster_name")
            };
            machine.zone = {
                id: 1,
                name: makeName("zone")
            };
            machine.architecture = makeName("arch");
            machine.power.type = {
                name: "ether_wake"
            };
            machine.power.parameters = {
                mac_address: "00:11:22:33:44:55"
            };
            machine.macs[0].mac = '00:11:22:33:44:55';
            machine.macs[0].error = false;
            machine.macs[1].mac = '00:11:22:33:44:66';
            machine.macs[1].error = false;

            spyOn(NodesManager, "create").and.returnValue($q.defer().promise);

            $scope.actionAddMachines();
            expect(NodesManager.create).toHaveBeenCalledWith({
                hostname: machine.name,
                architecture: machine.architecture,
                pxe_mac: machine.macs[0].mac,
                extra_macs: [machine.macs[1].mac],
                power_type: machine.power.type.name,
                power_parameters: machine.power.parameters,
                zone: {
                    id: machine.zone.id,
                    name: machine.zone.name
                },
                nodegroup: {
                    id: machine.cluster.id,
                    uuid: machine.cluster.uuid,
                    cluster_name: machine.cluster.cluster_name
                }
            });
        });
    });

    describe("actionAddChassis", function() {

        it("does nothing if errors", function() {
            var controller = makeController();
            var chassis = $scope.chassis;
            spyOn($scope, "chassisHasErrors").and.returnValue(true);
            $scope.actionAddChassis();
            expect($scope.chassis).toBe(chassis);
        });

        it("resets chassis", function() {
            var controller = makeController();
            var chassis = {
                cluster: {
                    uuid: makeName("uuid")
                },
                power: {
                    type: {
                        name: makeName("model"),
                        fields: []
                    },
                    parameters: {}
                }
            };
            $scope.chassis = chassis;
            $scope.actionAddChassis();
            expect($scope.chassis).not.toBe(chassis);
        });

        it("calls $http with correct parameters", function() {
            $http = jasmine.createSpy("$http");
            $http.and.returnValue($q.defer().promise);
            var controller = makeController();
            var uuid = makeName("uuid");
            var model = makeName("model");
            var parameters = {
                "one": makeName("one"),
                "two": makeName("two")
            };
            $scope.chassis = {
                cluster: {
                    uuid: uuid
                },
                power: {
                    type: {
                        name: model,
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
                    parameters: parameters
                }
            };
            $scope.actionAddChassis();
            parameters.model = model;
            expect($http).toHaveBeenCalledWith({
                method: 'POST',
                url: 'api/1.0/nodegroups/' + uuid +
                    '/?op=probe_and_enlist_hardware',
                data: $.param(parameters),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            });
        });

        it("calls hide", function() {
            var controller = makeController();
            var chassis = {
                cluster: {
                    uuid: makeName("uuid")
                },
                power: {
                    type: {
                        name: makeName("model"),
                        fields: []
                    },
                    parameters: {}
                }
            };
            $scope.chassis = chassis;
            spyOn($scope, "hide");
            $scope.actionAddChassis();
            expect($scope.hide).toHaveBeenCalled();
        });
    });
});
