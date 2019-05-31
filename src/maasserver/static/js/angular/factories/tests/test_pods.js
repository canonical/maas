/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for PodsManager.
 */

import { makeFakeResponse, makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("PodsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the PodsManager.
  var PodsManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    PodsManager = $injector.get("PodsManager");
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

  // Make a fake pod.
  function makePod() {
    return {
      id: makeInteger(0, 5000),
      name: makeName("pod")
    };
  }

  it("set requires attributes", function() {
    expect(PodsManager._pk).toBe("id");
    expect(PodsManager._handler).toBe("pod");
  });

  describe("refresh", function() {
    it("calls pod.refresh with params", function(done) {
      var pod = makePod();
      webSocket.returnData.push(makeFakeResponse("created"));
      PodsManager.refresh(pod).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("pod.refresh");
        expect(sentObject.params.id).toBe(pod.id);
        expect(sentObject.params.name).toBe(pod.name);
        done();
      });
    });
  });

  describe("compose", function() {
    it("calls pod.compose with params", function(done) {
      var pod = makePod();
      var params = {
        id: pod.id,
        cores: makeInteger(0, 10)
      };
      webSocket.returnData.push(makeFakeResponse("created"));
      PodsManager.compose(params).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("pod.compose");
        expect(sentObject.params.id).toBe(params.id);
        expect(sentObject.params.cores).toBe(params.cores);
        done();
      });
    });
  });
});
