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
        expect(NodesManager._activeNode).toBeNull();
        expect(NodesManager._pk).toBe("system_id");
        expect(NodesManager._handler).toBe("node");
        expect(NodesManager._metadataAttributes).toEqual(["status", "owner"]);
    });

    describe("getActiveNode", function() {

        it("returns active node", function() {
            var node = makeNode();
            NodesManager._activeNode = node;
            expect(NodesManager.getActiveNode()).toBe(node);
        });
    });

    describe("setActiveNode", function() {

        it("calls node.get and updates activeNode", function(done) {
            var otherNode = makeNode();
            var node = makeNode();
            NodesManager._activeNode = otherNode;
            webSocket.returnData.push(makeFakeResponse(node));
            NodesManager.setActiveNode(node).then(function(node) {
                expect(
                    angular.fromJson(
                        webSocket.sentData[0]).method).toBe("node.get");
                expect(NodesManager._activeNode).toEqual(node);
                done();
            });
        });

        it("clears activeNode", function(done) {
            var otherNode = makeNode();
            var node = makeNode();
            NodesManager._activeNode = otherNode;
            webSocket.returnData.push(makeFakeResponse("error", true));
            NodesManager.setActiveNode(node).then(null, function(node) {
                expect(NodesManager._activeNode).toBeNull();
                done();
            });
        });
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
                done();
            });
        });
    });
});
