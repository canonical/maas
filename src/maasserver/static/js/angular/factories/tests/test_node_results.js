/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultsManager.
 */


describe("NodeResultsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the NodeResultsManager and RegionConnection factory.
    var NodeResultsManager, RegionConnection, websocket;
    beforeEach(inject(function($injector) {
        NodeResultsManager = $injector.get("NodeResultsManager");
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

    it("set requires attributes", function() {
        expect(NodeResultsManager._pk).toBe("id");
        expect(NodeResultsManager._handler).toBe("noderesult");
    });

    // Make a random script result.
    function makescriptresult() {
        var script_result = {
            script: {
                id: makeInteger(0, 100)
            },
            output: makeName("output")
        };
        return script_result;
    }

    describe("get_result_data", function() {

        it("calls NodeResultHandler.get_result_data", function(done) {
            var script_result = makescriptresult();
            var script_id = script_result.script.id;
            var data_type = "output";
            webSocket.returnData.push(makeFakeResponse(script_result.output));
            NodeResultsManager.get_result_data(
                script_id, data_type).then(function() {
                    var sentObject = angular.fromJson(webSocket.sentData[0]);
                    expect(sentObject.method).toBe(
                        "noderesult.get_result_data");
                    expect(sentObject.params.script_id).toEqual(script_id);
                    expect(sentObject.params.data_type).toEqual(data_type);
                done();
            });
        });
    });
});
