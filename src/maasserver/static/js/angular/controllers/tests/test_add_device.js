/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for AddDeviceController.
 */

describe("AddDeviceController", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $q = $injector.get("$q");
    }));

    // Load the required dependencies for the AddDeviceController
    // and mock the websocket connection.
    var ClustersManager, DevicesManager, ManagerHelperService;
    var ValidationService, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        ClustersManager = $injector.get("ClustersManager");
        DevicesManager = $injector.get("DevicesManager");
        ManagerHelperService = $injector.get("ManagerHelperService");
        ValidationService = $injector.get("ValidationService");
        RegionConnection = $injector.get("RegionConnection");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Create the parent scope and the scope for the controller.
    var parentScope, $scope;
    beforeEach(function() {
        parentScope = $rootScope.$new();
        parentScope.addDeviceScope = null;
        $scope = parentScope.$new();
    });

    // Makes the AddDeviceController
    function makeController() {
        // Start the connection so a valid websocket is created in the
        // RegionConnection.
        RegionConnection.connect("");

        return $controller("AddDeviceController", {
            $scope: $scope,
            ClustersManager: ClustersManager,
            DevicesManager: DevicesManager,
            ValidationService: ValidationService,
            ManagerHelperService: ManagerHelperService
        });
    }

    // Generating random networks is difficult, so we just use an array
    // of random networks and select one from it.
    var networks = [
        {
            ip: "192.168.1.2",
            network: "192.168.1.0/24",
            subnet_mask: "255.255.255.0",
            broadcast_ip: "192.168.1.255",
            router_ip: "192.168.1.1",
            static_range: {
                low: "192.168.1.10",
                high: "192.168.1.149"
            },
            dynamic_range: {
                low: "192.168.1.150",
                high: "192.168.1.254"
            }
        },
        {
            ip: "192.168.2.2",
            network: "192.168.2.0/24",
            subnet_mask: "255.255.255.0",
            broadcast_ip: "192.168.2.255",
            router_ip: "192.168.2.1",
            static_range: {
                low: "192.168.2.10",
                high: "192.168.2.149"
            },
            dynamic_range: {
                low: "192.168.2.150",
                high: "192.168.2.254"
            }
        },
        {
            ip: "172.16.1.2",
            network: "172.16.0.0/16",
            subnet_mask: "255.255.0.0",
            broadcast_ip: "172.16.255.255",
            router_ip: "172.16.1.1",
            static_range: {
                low: "172.16.2.1",
                high: "172.16.3.254"
            },
            dynamic_range: {
                low: "172.16.4.1",
                high: "172.16.6.254"
            }
        },
        {
            ip: "172.17.1.2",
            network: "172.17.0.0/16",
            subnet_mask: "255.255.0.0",
            broadcast_ip: "172.17.255.255",
            router_ip: "172.17.1.1",
            static_range: {
                low: "172.17.2.1",
                high: "172.17.3.254"
            },
            dynamic_range: {
                low: "172.17.4.1",
                high: "172.17.6.254"
            }
        }
    ];
    var _nextNetwork = 0;
    beforeEach(function() {
        // Reset the next network before each test.
        _nextNetwork = 0;
    });

    // Make an unmanaged cluster interface.
    var _nicId = 0;
    function makeClusterInterface() {
        if(_nextNetwork >= networks.length) {
            throw new Error("Out of fake networks.");
        }
        var nic = networks[_nextNetwork++];
        nic.id = _nicId++;
        nic.management = 0;
        return nic;
    }

    // Make a managed cluster interface.
    function makeManagedClusterInterface() {
        var nic = makeClusterInterface();
        nic.management = 2;
        return nic;
    }

    // Make a cluster with give interfaces.
    var _clusterId = 0;
    function makeCluster(interfaces) {
        if(!angular.isArray(interfaces)) {
            interfaces = [makeManagedClusterInterface()];
        }
        return {
            id: _clusterId++,
            uuid: makeName("uuid"),
            interfaces: interfaces
        };
    }

    // Make a interface
    function makeInterface(mac, ipAssignment, clusterInterfaceId, ipAddress) {
        if(angular.isUndefined(mac)) {
            mac = "";
        }
        if(angular.isUndefined(ipAssignment)) {
            ipAssignment = null;
        }
        if(angular.isUndefined(clusterInterfaceId)) {
            clusterInterfaceId = null;
        }
        if(angular.isUndefined(ipAddress)) {
            ipAddress = "";
        }
        return {
            mac: mac,
            ipAssignment: ipAssignment,
            clusterInterfaceId: clusterInterfaceId,
            ipAddress: ipAddress
        };
    }

    it("sets addDeviceScope on $scope.$parent", function() {
        var controller = makeController();
        expect(parentScope.addDeviceScope).toBe($scope);
    });

    it("sets initial values on $scope", function() {
        var controller = makeController();
        expect($scope.viewable).toBe(false);
        expect($scope.clusters).toBe(ClustersManager.getItems());
        expect($scope.error).toBe(null);
        expect($scope.ipAssignments).toEqual([
            {
                name: "external",
                title: "External"
            },
            {
                name: "dynamic",
                title: "Dynamic"
            },
            {
                name: "static",
                title: "Static"
            }
        ]);
        expect($scope.device).toEqual({
            name: "",
            interfaces: [{
                mac: "",
                ipAssignment: null,
                clusterInterfaceId: null,
                ipAddress: ""
            }]
        });
    });

    it("calls loadManager with ClustersManagers", function() {
        spyOn(ManagerHelperService, "loadManager");
        var controller = makeController();
        expect(ManagerHelperService.loadManager).toHaveBeenCalledWith(
            ClustersManager);
    });

    describe("show", function() {

        it("does nothing if already viewable", function() {
            var controller = makeController();
            $scope.viewable = true;
            var name = makeName("name");
            $scope.device.name = name;
            $scope.show();
            // The device name should have stayed the same, showing that
            // the call did nothing.
            expect($scope.device.name).toBe(name);
        });

        it("clears device and sets viewable to true", function() {
            var controller = makeController();
            $scope.device.name = makeName("name");
            $scope.show();
            expect($scope.device.name).toBe("");
            expect($scope.viewable).toBe(true);
        });
    });

    describe("hide", function() {

        it("sets viewable to false", function() {
            var controller = makeController();
            $scope.viewable = true;
            $scope.hide();
            expect($scope.viewable).toBe(false);
        });

        it("emits event addDeviceHidden", function(done) {
            var controller = makeController();
            $scope.viewable = true;
            $scope.$on("addDeviceHidden", function() {
                done();
            });
            $scope.hide();
        });
    });

    describe("getManagedInterfaces", function() {

        it("returns only managed interfaces", function() {
            var controller = makeController();
            var managedInterfaces = [
                makeManagedClusterInterface(),
                makeManagedClusterInterface(),
                makeManagedClusterInterface()
                ];
            $scope.clusters = [
                makeCluster([]),
                makeCluster([managedInterfaces[0]]),
                makeCluster([managedInterfaces[1], makeClusterInterface()]),
                makeCluster([managedInterfaces[2]])
                ];
            expect($scope.getManagedInterfaces()).toEqual(managedInterfaces);
        });
    });

    describe("getInterfaceStaticRange", function() {

        it("returns text including low and high of static range", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            $scope.clusters = [
                makeCluster([nic])
                ];
            expect($scope.getInterfaceStaticRange(nic.id)).toEqual(
                nic.static_range.low + " - " + nic.static_range.high +
                " (Optional)");
        });
    });

    describe("nameHasError", function() {

        it("returns false if name is empty", function() {
            var controller = makeController();
            expect($scope.nameHasError()).toBe(false);
        });

        it("returns false if valid name", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            expect($scope.nameHasError()).toBe(false);
        });

        it("returns true if invalid name", function() {
            var controller = makeController();
            $scope.device.name = "a_bc.local";
            expect($scope.nameHasError()).toBe(true);
        });
    });

    describe("macHasError", function() {

        it("returns false if mac is empty", function() {
            var controller = makeController();
            var nic = makeInterface();
            expect($scope.macHasError(nic)).toBe(false);
        });

        it("returns false if valid mac", function() {
            var controller = makeController();
            var nic = makeInterface("00:00:11:22:33:44");
            expect($scope.macHasError(nic)).toBe(false);
        });

        it("returns false if not repeat mac", function() {
            var controller = makeController();
            var nic = makeInterface("00:00:11:22:33:44");
            var nic2 = makeInterface("00:00:11:22:33:55");
            $scope.device.interfaces = [
                nic,
                nic2
            ];
            expect($scope.macHasError(nic)).toBe(false);
            expect($scope.macHasError(nic2)).toBe(false);
        });

        it("returns true if invalid mac", function() {
            var controller = makeController();
            var nic = makeInterface("00:00:11:22:33");
            expect($scope.macHasError(nic)).toBe(true);
        });

        it("returns true if repeat mac", function() {
            var controller = makeController();
            var nic = makeInterface("00:00:11:22:33:44");
            var nic2 = makeInterface("00:00:11:22:33:44");
            $scope.device.interfaces = [
                nic,
                nic2
            ];
            expect($scope.macHasError(nic)).toBe(true);
            expect($scope.macHasError(nic2)).toBe(true);
        });
    });

    describe("ipHasError", function() {

        it("returns false if ip is empty", function() {
            var controller = makeController();
            var nic = makeInterface();
            expect($scope.ipHasError(nic)).toBe(false);
        });

        it("returns false if valid ipv4", function() {
            var controller = makeController();
            var nic = makeInterface();
            nic.ipAddress = "192.168.1.1";
            expect($scope.ipHasError(nic)).toBe(false);
        });

        it("returns false if valid ipv6", function() {
            var controller = makeController();
            var nic = makeInterface();
            nic.ipAddress = "2001:db8::1";
            expect($scope.ipHasError(nic)).toBe(false);
        });

        it("returns true if invalid ipv4", function() {
            var controller = makeController();
            var nic = makeInterface();
            nic.ipAddress = "192.168.1";
            expect($scope.ipHasError(nic)).toBe(true);
        });

        it("returns true if invalid ipv6", function() {
            var controller = makeController();
            var nic = makeInterface();
            nic.ipAddress = "2001::db8::1";
            expect($scope.ipHasError(nic)).toBe(true);
        });

        it("returns false if external ip out of managed network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            // No class A address is in the fake networks.
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = "10.0.1.1";
            deviceInterface.ipAssignment = {
                name: "external"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(false);
        });

        it("returns true if external ip in managed network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = nic.static_range.low;
            deviceInterface.ipAssignment = {
                name: "external"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(true);
        });

        it("returns false if static in managed network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = nic.static_range.low;
            deviceInterface.ipAssignment = {
                name: "static"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(false);
        });

        it("returns false if static ip in select network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = nic.static_range.low;
            deviceInterface.clusterInterfaceId = nic.id;
            deviceInterface.ipAssignment = {
                name: "static"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(false);
        });

        it("returns true if static ip out of select network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var otherNic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = otherNic.static_range.low;
            deviceInterface.clusterInterfaceId = nic.id;
            deviceInterface.ipAssignment = {
                name: "static"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(true);
        });

        it("returns true if static ip in dynamic range of network", function() {
            var controller = makeController();
            var nic = makeManagedClusterInterface();
            var cluster = makeCluster([nic]);
            $scope.clusters = [cluster];
            var deviceInterface = makeInterface();
            deviceInterface.ipAddress = nic.dynamic_range.low;
            deviceInterface.clusterInterfaceId = nic.id;
            deviceInterface.ipAssignment = {
                name: "static"
            };
            expect($scope.ipHasError(deviceInterface)).toBe(true);
        });
    });

    describe("deviceHasError", function() {

        it("returns true if name empty", function() {
            var controller = makeController();
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns true if mac empty", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns true if name invalid", function() {
            var controller = makeController();
            $scope.device.name = "ab_c.local";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns true if mac invalid", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44';
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns true if missing ip assignment selection", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns false if dynamic ip assignment selection", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            expect($scope.deviceHasError()).toBe(false);
        });

        it("returns true if external ip assignment and ip empty", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "external"
            };
            $scope.device.interfaces[0].ipAddress = "";
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns true if external ip assignment and ip invalid", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "external"
            };
            $scope.device.interfaces[0].ipAddress = "192.168";
            expect($scope.deviceHasError()).toBe(true);
        });

        it("returns false if external ip assignment and ip valid", function() {
            var controller = makeController();
            $scope.device.name = "abc";
            $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
            $scope.device.interfaces[0].ipAssignment = {
                name: "external"
            };
            $scope.device.interfaces[0].ipAddress = "192.168.1.1";
            expect($scope.deviceHasError()).toBe(false);
        });

        it("returns true if static ip assignment and no cluster interface",
            function() {
                var controller = makeController();
                $scope.device.name = "abc";
                $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
                $scope.device.interfaces[0].ipAssignment = {
                    name: "static"
                };
                expect($scope.deviceHasError()).toBe(true);
            });

        it("returns false if static ip assignment and cluster interface",
            function() {
                var controller = makeController();
                var nic = makeManagedClusterInterface();
                var cluster = makeCluster([nic]);
                $scope.clusters = [cluster];
                $scope.device.name = "abc";
                $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
                $scope.device.interfaces[0].ipAssignment = {
                    name: "static"
                };
                $scope.device.interfaces[0].clusterInterfaceId = nic.id;
                expect($scope.deviceHasError()).toBe(false);
            });

        it("returns true if static ip assignment, cluster interface, and " +
            "invalid ip address",
            function() {
                var controller = makeController();
                var nic = makeManagedClusterInterface();
                var cluster = makeCluster([nic]);
                $scope.clusters = [cluster];
                $scope.device.name = "abc";
                $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
                $scope.device.interfaces[0].ipAssignment = {
                    name: "static"
                };
                $scope.device.interfaces[0].clusterInterfaceId = nic.id;
                $scope.device.interfaces[0].ipAddress = "192.168";
                expect($scope.deviceHasError()).toBe(true);
            });

        it("returns true if static ip assignment, cluster interface, and " +
            "ip address out of network",
            function() {
                var controller = makeController();
                var nic = makeManagedClusterInterface();
                var otherNic = makeManagedClusterInterface();
                var cluster = makeCluster([nic]);
                $scope.clusters = [cluster];
                $scope.device.name = "abc";
                $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
                $scope.device.interfaces[0].ipAssignment = {
                    name: "static"
                };
                $scope.device.interfaces[0].clusterInterfaceId = nic.id;
                $scope.device.interfaces[0].ipAddress =
                    otherNic.static_range.low;
                expect($scope.deviceHasError()).toBe(true);
            });

        it("returns false if static ip assignment, cluster interface, and " +
            "ip address in network",
            function() {
                var controller = makeController();
                var nic = makeManagedClusterInterface();
                var cluster = makeCluster([nic]);
                $scope.clusters = [cluster];
                $scope.device.name = "abc";
                $scope.device.interfaces[0].mac = '00:11:22:33:44:55';
                $scope.device.interfaces[0].ipAssignment = {
                    name: "static"
                };
                $scope.device.interfaces[0].clusterInterfaceId = nic.id;
                $scope.device.interfaces[0].ipAddress = nic.static_range.low;
                expect($scope.deviceHasError()).toBe(false);
            });
    });

    describe("addInterface", function() {

        it("adds another interface", function() {
            var controller = makeController();
            $scope.addInterface();
            expect($scope.device.interfaces.length).toBe(2);
        });
    });

    describe("isPrimaryInterface", function() {

        it("returns true for first interface", function() {
            var controller = makeController();
            $scope.addInterface();
            expect(
                $scope.isPrimaryInterface(
                    $scope.device.interfaces[0])).toBe(true);
        });

        it("returns false for second interface", function() {
            var controller = makeController();
            $scope.addInterface();
            expect(
                $scope.isPrimaryInterface(
                    $scope.device.interfaces[1])).toBe(false);
        });
    });

    describe("deleteInterface", function() {

        it("doesnt remove primary interface", function() {
            var controller = makeController();
            var nic = $scope.device.interfaces[0];
            $scope.deleteInterface(nic);
            expect($scope.device.interfaces[0]).toBe(nic);
        });

        it("removes interface", function() {
            var controller = makeController();
            $scope.addInterface();
            var nic = $scope.device.interfaces[1];
            $scope.deleteInterface(nic);
            expect($scope.device.interfaces.indexOf(nic)).toBe(-1);
        });
    });

    describe("cancel", function() {

        it("clears error", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            $scope.cancel();
            expect($scope.error).toBeNull();
        });

        it("clears device", function() {
            var controller = makeController();
            $scope.device.name = makeName("name");
            $scope.cancel();
            expect($scope.device.name).toBe("");
        });

        it("calls hide", function() {
            var controller = makeController();
            spyOn($scope, "hide");
            $scope.cancel();
            expect($scope.hide).toHaveBeenCalled();
        });
    });

    describe("save", function() {

        it("doest nothing if device in error", function() {
            var controller = makeController();
            var error = makeName("error");
            $scope.error = error;
            spyOn($scope, "deviceHasError").and.returnValue(true);
            $scope.save();
            // Error would have been cleared if save did anything.
            expect($scope.error).toBe(error);
        });

        it("clears error before calling create", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "deviceHasError").and.returnValue(false);
            spyOn(DevicesManager, "create").and.returnValue(
                $q.defer().promise);
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            $scope.save();
            expect($scope.error).toBeNull();
        });

        it("calls create with converted device", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "deviceHasError").and.returnValue(false);
            spyOn(DevicesManager, "create").and.returnValue(
                $q.defer().promise);
            var name = makeName("name");
            var mac = makeName("mac");
            var assignment = "static";
            var nicId = makeInteger();
            var ipAddress = makeName("ip");
            $scope.device = {
                name: name,
                interfaces: [{
                    mac: mac,
                    ipAssignment: {
                        name: assignment
                    },
                    clusterInterfaceId: nicId,
                    ipAddress: ipAddress
                }]
            };
            $scope.save();
            expect(DevicesManager.create).toHaveBeenCalledWith({
                hostname: name,
                primary_mac: mac,
                extra_macs: [],
                interfaces: [{
                    mac: mac,
                    ip_assignment: assignment,
                    ip_address: ipAddress,
                    "interface": nicId
                }]
            });
        });

        it("on create resolve device is cleared", function() {
            var controller = makeController();
            $scope.error = makeName("error");
            spyOn($scope, "deviceHasError").and.returnValue(false);
            var defer = $q.defer();
            spyOn(DevicesManager, "create").and.returnValue(defer.promise);
            $scope.device.name = makeName("name");
            $scope.device.interfaces[0].ipAssignment = {
                name: "dynamic"
            };
            $scope.save();
            defer.resolve();
            $rootScope.$digest();
            expect($scope.device.name).toBe("");
        });

        it("on create resolve hide is called when addAnother is false",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "deviceHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DevicesManager, "create").and.returnValue(defer.promise);
                $scope.device.name = makeName("name");
                $scope.device.interfaces[0].ipAssignment = {
                    name: "dynamic"
                };
                spyOn($scope, "hide");
                $scope.save(false);
                defer.resolve();
                $rootScope.$digest();
                expect($scope.hide).toHaveBeenCalled();
            });

        it("on create resolve hide is not called when addAnother is true",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "deviceHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DevicesManager, "create").and.returnValue(defer.promise);
                $scope.device.name = makeName("name");
                $scope.device.interfaces[0].ipAssignment = {
                    name: "dynamic"
                };
                spyOn($scope, "hide");
                $scope.save(true);
                defer.resolve();
                $rootScope.$digest();
                expect($scope.hide).not.toHaveBeenCalled();
            });

        it("on create reject error is set",
            function() {
                var controller = makeController();
                $scope.error = makeName("error");
                spyOn($scope, "deviceHasError").and.returnValue(false);
                var defer = $q.defer();
                spyOn(DevicesManager, "create").and.returnValue(defer.promise);
                $scope.device.name = makeName("name");
                $scope.device.interfaces[0].ipAssignment = {
                    name: "dynamic"
                };
                $scope.save();
                var errorMsg = makeName("error");
                var error = "{'hostname': ['" + errorMsg + "']}";
                defer.reject(error);
                $rootScope.$digest();
                expect($scope.error).toBe(errorMsg + "  ");
            });
    });

    describe("convertPythonDictToErrorMsg", function() {
        it("converts hostname error for display",
            function() {
                var controller = makeController();
                var errorMsg = makeName("error");
                var error = "{'hostname': ['Node " + errorMsg + "']}";
                var expected = "Device " + errorMsg + "  ";
                expect($scope.convertPythonDictToErrorMsg(
                        error)).toBe(expected);
        });

        it("converts mac_addresses error for display",
                function() {
                    var controller = makeController();
                    var errorMsg = makeName("error");
                    var error = "{'mac_addresses': ['" + errorMsg + "']}";
                    var expected = errorMsg + "  ";
                    expect($scope.convertPythonDictToErrorMsg(
                            error)).toBe(expected);
        });

        it("converts unknown segments by default",
                function() {
                    var controller = makeController();
                    var errorSegment1 = makeName("error");
                    var errorSegment2 = makeName("error");
                    var error = "{'" + errorSegment1 +
                        "': ['" + errorSegment2 + "']}";
                    var expected = errorSegment1 + errorSegment2;
                    expect($scope.convertPythonDictToErrorMsg(
                            error)).toBe(expected);
        });
    });
});
