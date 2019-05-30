/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DHCPSnippetsManager.
 */

import { makeFakeResponse, makeName } from "testing/utils";

describe("DHCPSnippetsManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the DHCPSnippetsManagera nd RegionConnection factory.
  var DHCPSnippetsManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
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

  // Make a random snippet.
  function makeDHCPSnippet() {
    return {
      name: makeName("name"),
      enabled: true,
      value: makeName("value")
    };
  }

  it("set requires attributes", function() {
    expect(DHCPSnippetsManager._pk).toBe("id");
    expect(DHCPSnippetsManager._handler).toBe("dhcpsnippet");
  });

  describe("create", function() {
    it("calls dhcpsnippet.create with params", function(done) {
      var snippet = makeDHCPSnippet();
      webSocket.returnData.push(makeFakeResponse(snippet));
      DHCPSnippetsManager.create(snippet).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("dhcpsnippet.create");
        expect(sentObject.params).toEqual(snippet);
        done();
      });
    });
  });
});
