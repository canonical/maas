/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SwitchesManager.
 */

import { makeFakeResponse, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("SwitchesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the SwitchesManager and RegionConnection factory.
  var RegionConnection, SwitchesManager, webSocket;
  beforeEach(inject(function($injector) {
    SwitchesManager = $injector.get("SwitchesManager");
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
    expect(SwitchesManager._pk).toBe("system_id");
    expect(SwitchesManager._handler).toBe("switch");
    expect(Object.keys(SwitchesManager._metadataAttributes)).toEqual([
      "owner",
      "subnets",
      "tags",
      "zone"
    ]);
  });

  describe("performAction", function() {
    it("calls switch.action with system_id and action", function(done) {
      var device = makeDevice();
      webSocket.returnData.push(makeFakeResponse("deleted"));
      SwitchesManager.performAction(device, "delete").then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("switch.action");
        expect(sentObject.params.system_id).toBe(device.system_id);
        expect(sentObject.params.action).toBe("delete");
        expect(sentObject.params.extra).toEqual({});
        done();
      });
    });

    it("calls switch.action with extra", function(done) {
      var device = makeDevice();
      var extra = {
        osystem: makeName("os")
      };
      webSocket.returnData.push(makeFakeResponse("deployed"));
      SwitchesManager.performAction(device, "deploy", extra).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("switch.action");
        expect(sentObject.params.system_id).toBe(device.system_id);
        expect(sentObject.params.action).toBe("deploy");
        expect(sentObject.params.extra).toEqual(extra);
        done();
      });
    });
  });
});
