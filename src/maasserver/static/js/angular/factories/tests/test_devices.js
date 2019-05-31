/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DevicesManager.
 */

import { makeFakeResponse, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("DevicesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

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
    if (angular.isDefined(selected)) {
      device.$selected = selected;
    }
    return device;
  }

  it("set requires attributes", function() {
    expect(DevicesManager._pk).toBe("system_id");
    expect(DevicesManager._handler).toBe("device");
    expect(Object.keys(DevicesManager._metadataAttributes)).toEqual([
      "owner",
      "subnets",
      "tags",
      "zone"
    ]);
  });

  describe("createInferface", function() {
    it("calls device.create_interface with params", function(done) {
      var device = makeDevice();
      webSocket.returnData.push(makeFakeResponse(device));
      spyOn(DevicesManager, "_replaceItem");
      DevicesManager.createInterface(device).then(function(obj) {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("device.create_interface");
        expect(sentObject.params.system_id).toBe(device.system_id);
        expect(DevicesManager._replaceItem).toHaveBeenCalledWith(obj);
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
      DevicesManager.performAction(device, "deploy", extra).then(function() {
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
