/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for PackageRepositoriesManager.
 */

import { makeFakeResponse, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("PackageRepositoriesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the PackageRepositoriesManager and RegionConnection factory.
  var PackageRepositoriesManager, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    PackageRepositoriesManager = $injector.get("PackageRepositoriesManager");
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

  // Make a random repo.
  function makePackageRepository() {
    return {
      name: makeName("name"),
      enabled: true,
      url: makeName("url")
    };
  }

  it("set requires attributes", function() {
    expect(PackageRepositoriesManager._pk).toBe("id");
    expect(PackageRepositoriesManager._handler).toBe("packagerepository");
  });

  describe("create", function() {
    it("calls packagerepository.create with params", function(done) {
      var obj = makePackageRepository();
      webSocket.returnData.push(makeFakeResponse(obj));
      PackageRepositoriesManager.create(obj).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("packagerepository.create");
        expect(sentObject.params).toEqual(obj);
        done();
      });
    });
  });
});
