/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for MachinesManager.
 */


describe("MachinesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the MachinesManager and RegionConnection factory.
    var MachinesManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        MachinesManager = $injector.get("MachinesManager");
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
        expect(MachinesManager._pk).toBe("system_id");
        expect(MachinesManager._handler).toBe("machine");
    });

    it("set requires attributes", function() {
        expect(Object.keys(MachinesManager._metadataAttributes)).toEqual(
            ["status", "owner", "tags", "zone", "subnets", "fabrics",
            "spaces", "storage_tags"]);
    });
});
