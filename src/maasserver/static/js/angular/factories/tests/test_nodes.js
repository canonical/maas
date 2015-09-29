/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodesManager.
 */


describe("NodesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the NodesManager and RegionConnection factory.
    var NodesManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
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

    // Make a random node.
    function makeNode(selected) {
        var node = {
            system_id: makeName("system_id"),
            name: makeName("name"),
            status: makeName("status"),
            owner: makeName("owner")
        };
        if(angular.isDefined(selected)) {
            node.$selected = selected;
        }
        return node;
    }

    it("set requires attributes", function() {
        expect(NodesManager._pk).toBe("system_id");
        expect(NodesManager._handler).toBe("node");
        expect(Object.keys(NodesManager._metadataAttributes)).toEqual(
            ["status", "owner", "tags", "zone", "networks", "storage_tags"]);
    });

    describe("create", function() {

        it("calls node.create with node", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse(node));
            NodesManager.create(node).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create");
                expect(sentObject.params).toEqual(node);
                done();
            });
        });
    });

    describe("performAction", function() {

        it("calls node.action with system_id and action", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse("deleted"));
            NodesManager.performAction(node, "delete").then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.action");
                expect(sentObject.params.system_id).toBe(node.system_id);
                expect(sentObject.params.action).toBe("delete");
                expect(sentObject.params.extra).toEqual({});
                done();
            });
        });

        it("calls node.action with extra", function(done) {
            var node = makeNode();
            var extra = {
                osystem: makeName("os")
            };
            webSocket.returnData.push(makeFakeResponse("deployed"));
            NodesManager.performAction(node, "deploy", extra).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.action");
                expect(sentObject.params.system_id).toBe(node.system_id);
                expect(sentObject.params.action).toBe("deploy");
                expect(sentObject.params.extra).toEqual(extra);
                done();
            });
        });
    });

    describe("checkPowerState", function() {

        it("calls node.check_power with system_id", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse("on"));
            NodesManager.checkPowerState(node).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.check_power");
                expect(sentObject.params.system_id).toBe(node.system_id);
                done();
            });
        });

        it("sets power_state to results", function(done) {
            var node = makeNode();
            var power_state = makeName("state");
            webSocket.returnData.push(makeFakeResponse(power_state));
            NodesManager.checkPowerState(node).then(function(state) {
                expect(node.power_state).toBe(power_state);
                expect(state).toBe(power_state);
                done();
            });
        });

        it("sets power_state to error on error and logs error",
            function(done) {
                var node = makeNode();
                var error = makeName("error");
                spyOn(console, "log");
                webSocket.returnData.push(makeFakeResponse(error, true));
                NodesManager.checkPowerState(node).then(function(state) {
                    expect(node.power_state).toBe("error");
                    expect(state).toBe("error");
                    expect(console.log).toHaveBeenCalledWith(error);
                    done();
                });
            });
    });

    describe("updateInterface", function() {

        it("calls node.update_interface with system_id and interface_id",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.updateInterface(node, interface_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.update_interface");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        done();
                    });
            });

        it("calls node.update_interface with params",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                var params = {
                    name: makeName("eth0")
                };
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.updateInterface(node, interface_id, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.update_interface");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        expect(sentObject.params.name).toBe(params.name);
                        done();
                    });
            });
    });
});
