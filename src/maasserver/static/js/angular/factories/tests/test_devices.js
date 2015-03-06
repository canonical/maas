/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DevicesManager.
 */


describe("DevicesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the DevicesManager and RegionConnection factory.
    var DevicesManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        DevicesManager = $injector.get("DevicesManager");
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

    // Make a random device.
    function makeDevice(selected) {
        var device = {
            system_id: makeName("system_id"),
            name: makeName("name"),
            owner: makeName("owner")
        };
        if(angular.isDefined(selected)) {
            device.$selected = selected;
        }
        return device;
    }

    it("set requires attributes", function() {
        expect(DevicesManager._activeDevice).toBeNull();
        expect(DevicesManager._pk).toBe("system_id");
        expect(DevicesManager._handler).toBe("device");
        expect(DevicesManager._metadataAttributes).toEqual(["owner"]);
    });

    describe("getActiveDevice", function() {

        it("returns active device", function() {
            var device = makeDevice();
            DevicesManager._activeDevice = device;
            expect(DevicesManager.getActiveDevice()).toBe(device);
        });
    });

    describe("setActiveDevice", function() {

        it("calls device.get and updates _activeDevice", function(done) {
            var otherDevice = makeDevice();
            var device = makeDevice();
            DevicesManager._activeDevice = otherDevice;
            webSocket.returnData.push(makeFakeResponse(device));
            DevicesManager.setActiveDevice(device).then(function(device) {
                expect(
                    angular.fromJson(
                        webSocket.sentData[0]).method).toBe("device.get");
                expect(DevicesManager._activeDevice).toEqual(device);
                done();
            });
        });

        it("clears activeDevice", function(done) {
            var otherDevice = makeDevice();
            var device = makeDevice();
            DevicesManager._activeDevice = otherDevice;
            webSocket.returnData.push(makeFakeResponse("error", true));
            DevicesManager.setActiveDevice(device).then(null, function(device) {
                expect(DevicesManager._activeDevice).toBeNull();
                done();
            });
        });
    });

    describe("performAction", function() {

        it("calls device.action with system_id and action", function(done) {
            var device = makeDevice();
            webSocket.returnData.push(makeFakeResponse("deleted"));
            DevicesManager.performAction(device, "delete").then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("device.action");
                expect(sentObject.params.system_id).toBe(device.system_id);
                expect(sentObject.params.action).toBe("delete");
                expect(sentObject.params.extra).toEqual({});
                done();
            });
        });

        it("calls device.action with extra", function(done) {
            var device = makeDevice();
            var extra = {
                osystem: makeName("os")
            };
            webSocket.returnData.push(makeFakeResponse("deployed"));
            DevicesManager.performAction(device, "deploy", extra).then(
                function() {
                    var sentObject = angular.fromJson(webSocket.sentData[0]);
                    expect(sentObject.method).toBe("device.action");
                    expect(sentObject.params.system_id).toBe(device.system_id);
                    expect(sentObject.params.action).toBe("deploy");
                    expect(sentObject.params.extra).toEqual(extra);
                    done();
                });
        });
    });
});
