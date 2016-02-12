/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ControllersManager.
 */


describe("ControllersManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the ControllersManager and RegionConnection factory.
    var ControllersManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        ControllersManager = $injector.get("ControllersManager");
        RegionConnection = $injector.get("RegionConnection");

        // Mock buildSocket so an actual connection is not made.
        webSocket = new MockWebSocket();
        spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    // Open the connection to the region before each test.
    beforeEach(function(done) {
        RegionConnection.registerHandler("open", function() {
            done();
        });
        RegionConnection.connect("");
    });

    // Make a random controller.
    function makecontroller(selected) {
        var controller = {
            system_id: makeName("system_id"),
            name: makeName("name"),
            status: makeName("status"),
            owner: makeName("owner")
        };
        if(angular.isDefined(selected)) {
            controller.$selected = selected;
        }
        return controller;
    }

    it("set requires attributes", function() {
        expect(ControllersManager._pk).toBe("system_id");
        expect(ControllersManager._handler).toBe("controller");
        expect(Object.keys(ControllersManager._metadataAttributes)).toEqual([]);
    });

    describe("create", function() {

        it("calls controller.create with controller", function(done) {
            var controller = makecontroller();
            webSocket.returnData.push(makeFakeResponse(controller));
            ControllersManager.create(controller).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("controller.create");
                expect(sentObject.params).toEqual(controller);
                done();
            });
        });
    });

    describe("performAction", function() {

        it("calls controller.action with system_id and action", function(done) {
            var controller = makecontroller();
            webSocket.returnData.push(makeFakeResponse("deleted"));
            ControllersManager.performAction(
                    controller, "delete").then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("controller.action");
                expect(sentObject.params.system_id).toBe(controller.system_id);
                expect(sentObject.params.action).toBe("delete");
                expect(sentObject.params.extra).toEqual({});
                done();
            });
        });

        it("calls controller.action with extra", function(done) {
            var controller = makecontroller();
            var extra = {
                osystem: makeName("os")
            };
            webSocket.returnData.push(makeFakeResponse("deployed"));
            ControllersManager.performAction(
                controller, "deploy", extra).then(function() {
                    var sentObject = angular.fromJson(webSocket.sentData[0]);
                    expect(sentObject.method).toBe("controller.action");
                    expect(sentObject.params.system_id).toBe(
                            controller.system_id);
                    expect(sentObject.params.action).toBe("deploy");
                    expect(sentObject.params.extra).toEqual(extra);
                    done();
                });
        });
    });

    describe("checkPowerState", function() {

        it("calls controller.check_power with system_id", function(done) {
            var controller = makecontroller();
            webSocket.returnData.push(makeFakeResponse("on"));
            ControllersManager.checkPowerState(controller).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("controller.check_power");
                expect(sentObject.params.system_id).toBe(controller.system_id);
                done();
            });
        });

        it("sets power_state to results", function(done) {
            var controller = makecontroller();
            var power_state = makeName("state");
            webSocket.returnData.push(makeFakeResponse(power_state));
            ControllersManager.checkPowerState(
                    controller).then(function(state) {
                expect(controller.power_state).toBe(power_state);
                expect(state).toBe(power_state);
                done();
            });
        });

        it("sets power_state to error on error and logs error",
            function(done) {
                var controller = makecontroller();
                var error = makeName("error");
                spyOn(console, "log");
                webSocket.returnData.push(makeFakeResponse(error, true));
                ControllersManager.checkPowerState(
                        controller).then(function(state) {
                    expect(controller.power_state).toBe("error");
                    expect(state).toBe("error");
                    expect(console.log).toHaveBeenCalledWith(error);
                    done();
                });
            });
    });

    describe("createPhysicalInterface", function() {

        it("calls controller.create_physical with system_id without params",
            function(done) {
                var controller = makecontroller();
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createPhysicalInterface(
                        controller).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.create_physical");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    done();
                });
            });

        it("calls controller.create_physical with params",
            function(done) {
                var controller = makecontroller();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createPhysicalInterface(
                        controller, params).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.create_physical");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.vlan).toBe(params.vlan);
                    done();
                });
            });
    });

    describe("createVLANInterface", function() {

        it("calls controller.create_vlan with system_id without params",
            function(done) {
                var controller = makecontroller();
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createVLANInterface(controller).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "controller.create_vlan");
                        expect(sentObject.params.system_id).toBe(
                            controller.system_id);
                        done();
                    });
            });

        it("calls controller.create_vlan with params",
            function(done) {
                var controller = makecontroller();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createVLANInterface(
                        controller, params).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.create_vlan");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.vlan).toBe(params.vlan);
                    done();
                });
            });
    });

    describe("createBondInterface", function() {

        it("calls controller.create_bond with system_id without params",
            function(done) {
                var controller = makecontroller();
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createBondInterface(controller).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "controller.create_bond");
                        expect(sentObject.params.system_id).toBe(
                            controller.system_id);
                        done();
                    });
            });

        it("calls controller.create_bond with params",
            function(done) {
                var controller = makecontroller();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                ControllersManager.createBondInterface(
                        controller, params).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.create_bond");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.vlan).toBe(params.vlan);
                    done();
                });
            });
    });

    describe("updateInterface", function() {

        it("calls controller.update_interface with system_id and interface_id",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                ControllersManager.updateInterface(
                        controller, interface_id).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.update_interface");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.interface_id).toBe(
                        interface_id);
                    done();
                });
            });

        it("calls controller.update_interface with params",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                var params = {
                    name: makeName("eth0")
                };
                webSocket.returnData.push(makeFakeResponse("updated"));
                ControllersManager.updateInterface(
                        controller, interface_id, params).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.update_interface");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.interface_id).toBe(
                        interface_id);
                    expect(sentObject.params.name).toBe(params.name);
                    done();
                });
            });
    });

    describe("deleteInterface", function() {

        it("calls controller.delete_interface with correct params",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                ControllersManager.deleteInterface(
                        controller, interface_id).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.delete_interface");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.interface_id).toBe(
                        interface_id);
                    done();
                });
            });
    });

    describe("linkSubnet", function() {

        it("calls controller.link_subnet with system_id and interface_id",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                ControllersManager.linkSubnet(controller, interface_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "controller.link_subnet");
                        expect(sentObject.params.system_id).toBe(
                            controller.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        done();
                    });
            });

        it("calls controller.link_subnet with params",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                var params = {
                    name: makeName("eth0")
                };
                webSocket.returnData.push(makeFakeResponse("updated"));
                ControllersManager.linkSubnet(
                        controller, interface_id, params).then(function() {
                    var sentObject = angular.fromJson(
                        webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "controller.link_subnet");
                    expect(sentObject.params.system_id).toBe(
                        controller.system_id);
                    expect(sentObject.params.interface_id).toBe(
                        interface_id);
                    expect(sentObject.params.name).toBe(params.name);
                    done();
                });
            });
    });

    describe("unlinkSubnet", function() {

        it("calls controller.unlink_subnet with correct params",
            function(done) {
                var controller = makecontroller(), interface_id = makeInteger(
                    0, 100);
                var link_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                ControllersManager.unlinkSubnet(
                    controller, interface_id, link_id).then(
                        function() {
                            var sentObject = angular.fromJson(
                                webSocket.sentData[0]);
                            expect(sentObject.method).toBe(
                                "controller.unlink_subnet");
                            expect(sentObject.params.system_id).toBe(
                                controller.system_id);
                            expect(sentObject.params.interface_id).toBe(
                                interface_id);
                            expect(sentObject.params.link_id).toBe(
                                link_id);
                            done();
                        });
            });
    });

});
