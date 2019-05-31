/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ControllersManager.
 */

import { makeFakeResponse, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("ControllersManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

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
    if (angular.isDefined(selected)) {
      controller.$selected = selected;
    }
    return controller;
  }

  it("sanity check", function() {
    expect(ControllersManager._pk).toBe("system_id");
    expect(ControllersManager._handler).toBe("controller");
  });

  it("set requires attributes", function() {
    expect(Object.keys(ControllersManager._metadataAttributes)).toEqual([]);
  });

  describe("checkImageStates", function() {
    it("calls controller.check_images with system_ids", function(done) {
      var controllers = [makecontroller(), makecontroller()];
      var states = [makeName("state"), makeName("state")];
      let response = {};
      response[controllers[0].system_id] = states[0];
      response[controllers[1].system_id] = states[1];
      webSocket.returnData.push(makeFakeResponse(response));

      ControllersManager.checkImageStates(controllers).then(function(retval) {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("controller.check_images");
        expect(sentObject.params).toEqual(controllers);
        expect(retval).toEqual(response);
        done();
      });
    });
  });
});
