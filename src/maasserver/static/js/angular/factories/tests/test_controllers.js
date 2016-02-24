/* Copyright 2016 Canonical Ltd.  This software is licensed under the
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

    it("sanity check", function() {
        expect(ControllersManager._pk).toBe("system_id");
        expect(ControllersManager._handler).toBe("controller");
    });

    it("set requires attributes", function() {
        expect(Object.keys(ControllersManager._metadataAttributes)).toEqual([]);
    });

});
