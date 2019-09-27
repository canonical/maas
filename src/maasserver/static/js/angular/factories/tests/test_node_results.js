/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeResultsManagerFactory.
 */

import {
  makeBoolean,
  makeFakeResponse,
  makeInteger,
  makeName,
  pickItem
} from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("NodeResultsManagerFactory", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the NodeResultsManager and RegionConnection factory.
  var NodeResultsManagerFactory, RegionConnection, webSocket;
  beforeEach(inject(function($injector) {
    NodeResultsManagerFactory = $injector.get("NodeResultsManagerFactory");
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

  // Make a random node.
  function makenode() {
    return {
      system_id: makeName("system_id")
    };
  }

  it("set requires attributes", function() {
    var node = makenode();
    var nodeResultsManager = NodeResultsManagerFactory.getManager(node);
    expect(nodeResultsManager._pk).toBe("id");
    expect(nodeResultsManager._handler).toBe("noderesult");
    expect(nodeResultsManager._node).toEqual(node);
    expect(nodeResultsManager._factory).toEqual(NodeResultsManagerFactory);
    expect(nodeResultsManager.commissioning_results).toEqual([
      {
        title: null,
        hardware_type: 0,
        results: {}
      },
      {
        title: "CPU",
        hardware_type: 1,
        results: {}
      },
      {
        title: "Memory",
        hardware_type: 2,
        results: {}
      },
      {
        title: "Storage",
        hardware_type: 3,
        results: {}
      },
      {
        title: "Network",
        hardware_type: 4,
        results: {}
      }
    ]);
    expect(nodeResultsManager.testing_results).toEqual([
      {
        title: "CPU",
        hardware_type: 1,
        results: {}
      },
      {
        title: "Memory",
        hardware_type: 2,
        results: {}
      },
      {
        title: "Storage",
        hardware_type: 3,
        results: {}
      },
      {
        title: "Other Results",
        hardware_type: 0,
        results: {}
      },
      {
        title: "Network",
        hardware_type: 4,
        results: {}
      }
    ]);
    expect(nodeResultsManager.installation_results).toEqual([]);
  });

  describe("_processItem", function() {
    angular.forEach({ 0: "commissioning", 2: "testing" }, function(
      result_type_name,
      result_type
    ) {
      angular.forEach({ 0: "other", 1: "CPU", 2: "memory" }, function(
        hardware_type_name,
        hardware_type
      ) {
        it(
          "add " + result_type_name + " " + hardware_type_name + " result",
          function() {
            var node = makenode();
            var manager = NodeResultsManagerFactory.getManager(
              node,
              result_type_name
            );
            var result = {
              name: makeName("name"),
              status: makeInteger(0, 100),
              status_name: makeName("status_name"),
              result_type: parseInt(result_type, 10),
              hardware_type: parseInt(hardware_type, 10),
              physical_blockdevice: null,
              showing_results: false,
              showing_menu: false,
              showing_history: false,
              $selected: false
            };
            var results = [];
            var i;
            for (i = 0; i < manager.results.length; i++) {
              if (
                manager.results[i].hardware_type === parseInt(hardware_type, 10)
              ) {
                results = manager.results[i].results[null] = [];
                break;
              }
            }

            manager._processItem(result);
            expect(results).toEqual([result]);
          }
        );

        it(
          "update " + result_type_name + " " + hardware_type_name + " result",
          function() {
            var node = makenode();
            var manager = NodeResultsManagerFactory.getManager(
              node,
              result_type_name
            );
            var old_result = {
              name: makeName("name"),
              status: makeInteger(0, 100),
              status_name: makeName("status_name"),
              result_type: parseInt(result_type, 10),
              hardware_type: parseInt(hardware_type, 10),
              physical_blockdevice: null,
              showing_results: makeBoolean(),
              showing_menu: makeBoolean(),
              showing_history: makeBoolean(),
              $selected: makeBoolean()
            };
            var results = [];
            var i;
            for (i = 0; i < manager.results.length; i++) {
              if (
                manager.results[i].hardware_type === parseInt(hardware_type, 10)
              ) {
                results = manager.results[i].results[null] = [];
                break;
              }
            }
            results.push(old_result);
            var result_section = "tests";
            if (result_type_name === "commissioning") {
              result_section = "scripts";
            }
            var result = {
              name: old_result.name,
              status: makeInteger(0, 100),
              status_name: makeName("status_name"),
              result_type: parseInt(result_type, 10),
              result_section: result_section,
              hardware_type: parseInt(hardware_type, 10),
              physical_blockdevice: null,
              showing_results: false,
              showing_menu: false,
              showing_history: false,
              $selected: false
            };
            manager._processItem(result);
            expect(results).toEqual([
              {
                name: old_result.name,
                status: result.status,
                status_name: result.status_name,
                result_type: parseInt(result_type, 10),
                result_section: result_section,
                hardware_type: parseInt(hardware_type, 10),
                physical_blockdevice: null,
                showing_results: old_result.showing_results,
                showing_menu: old_result.showing_menu,
                showing_history: old_result.showing_history,
                $selected: old_result.$selected
              }
            ]);
          }
        );
      });

      it("add " + result_type_name + " network result", () => {
        const node = makenode();
        const manager = NodeResultsManagerFactory.getManager(
          node,
          result_type_name
        );
        const nic = {
          id: makeInteger(0, 100),
          name: makeName("name"),
          mac_address: makeName("mac_address")
        };

        node.interfaces = [nic];

        const resultTitle = `${nic.name} (${nic.mac_address})`;
        const resultSection =
          result_type_name === "commissioning" ? "scripts" : "tests";

        const result = {
          name: makeName("name"),
          status: makeInteger(0, 100),
          status_name: makeName("status_name"),
          result_type: parseInt(result_type, 10),
          result_section: resultSection,
          hardware_type: 4,
          showing_results: false,
          showing_menu: false,
          showing_history: false,
          $selected: false,
          interface: nic.id
        };

        let results = [];

        for (let i = 0, ii = manager.results.length; i < ii; i++) {
          if (manager.results[i].hardware_type === 4) {
            results = manager.results[i].results[resultTitle] = [];
            break;
          }
        }

        manager._processItem(result);
        expect(results).toEqual([result]);
      });

      it("add " + result_type_name + " storage result", function() {
        var node = makenode();
        node.disks = [
          {
            id: makeInteger(0, 100),
            name: makeName("name"),
            model: makeName("model"),
            serial: makeName("serial")
          }
        ];
        var manager = NodeResultsManagerFactory.getManager(
          node,
          result_type_name
        );
        var result_section =
          result_type_name === "commissioning" ? "scripts" : "tests";
        var result = {
          name: makeName("name"),
          status: makeInteger(0, 100),
          status_name: makeName("status_name"),
          result_type: parseInt(result_type, 10),
          result_section: result_section,
          hardware_type: 3,
          physical_blockdevice: node.disks[0].id,
          showing_results: false,
          showing_menu: false,
          showing_history: false,
          $selected: false
        };
        var subtext =
          "/dev/" +
          node.disks[0].name +
          " (Model: " +
          node.disks[0].model +
          ", Serial: " +
          node.disks[0].serial +
          ")";
        var results = [];
        var i;
        for (i = 0; i < manager.results.length; i++) {
          if (manager.results[i].hardware_type === 3) {
            results = manager.results[i].results[subtext] = [];
            break;
          }
        }

        manager._processItem(result);
        expect(results).toEqual([result]);
      });

      it("update " + result_type_name + " storage result", function() {
        var node = makenode();
        node.disks = [
          {
            id: makeInteger(0, 100),
            name: makeName("name"),
            model: makeName("model"),
            serial: makeName("serial")
          }
        ];
        var manager = NodeResultsManagerFactory.getManager(
          node,
          result_type_name
        );
        var old_result = {
          name: makeName("name"),
          status: makeInteger(0, 100),
          status_name: makeName("status_name"),
          result_type: parseInt(result_type, 10),
          hardware_type: 3,
          physical_blockdevice: node.disks[0].id,
          showing_results: makeBoolean(),
          showing_menu: makeBoolean(),
          showing_history: makeBoolean(),
          $selected: makeBoolean()
        };
        var subtext =
          "/dev/" +
          node.disks[0].name +
          " (Model: " +
          node.disks[0].model +
          ", Serial: " +
          node.disks[0].serial +
          ")";
        var results = [];
        var i;
        for (i = 0; i < manager.results.length; i++) {
          if (manager.results[i].hardware_type === 3) {
            results = manager.results[i].results[subtext] = [];
            break;
          }
        }
        results.push(old_result);
        var result_section =
          result_type_name === "commissioning" ? "scripts" : "tests";
        var result = {
          name: old_result.name,
          status: makeInteger(0, 100),
          status_name: makeName("status_name"),
          result_type: parseInt(result_type, 10),
          hardware_type: 3,
          physical_blockdevice: node.disks[0].id,
          showing_results: false,
          showing_menu: false,
          showing_history: false,
          $selected: false
        };
        manager._processItem(result);
        expect(results).toEqual([
          {
            name: old_result.name,
            status: result.status,
            status_name: result.status_name,
            result_type: parseInt(result_type, 10),
            result_section: result_section,
            hardware_type: 3,
            physical_blockdevice: node.disks[0].id,
            showing_results: old_result.showing_results,
            showing_menu: old_result.showing_menu,
            showing_history: old_result.showing_history,
            $selected: old_result.$selected
          }
        ]);
      });
    });

    // Installation results are stored in a signal list.
    it("add installation result", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "installation");
      var result = {
        name: makeName("name"),
        status: makeInteger(0, 100),
        status_name: makeName("status_name"),
        result_type: 1,
        hardware_type: 0,
        physical_blockdevice: null,
        showing_results: false,
        showing_menu: false,
        showing_history: false,
        $selected: false
      };
      manager._processItem(result);
      expect(manager.installation_results).toEqual([result]);
    });

    it("update installation result", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "installation");
      var old_result = {
        name: makeName("name"),
        status: makeInteger(0, 100),
        status_name: makeName("status_name"),
        result_type: 1,
        hardware_type: 0,
        physical_blockdevice: null,
        showing_results: makeBoolean(),
        showing_menu: makeBoolean(),
        showing_history: makeBoolean(),
        $selected: makeBoolean()
      };
      manager.installation_results.push(old_result);
      var result = {
        name: old_result.name,
        status: makeInteger(0, 100),
        status_name: makeName("status_name"),
        result_type: 1,
        result_section: "scripts",
        hardware_type: 0,
        physical_blockdevice: null,
        showing_results: false,
        showing_menu: false,
        showing_history: false,
        $selected: false
      };
      manager._processItem(result);
      expect(manager.installation_results).toEqual([
        {
          name: old_result.name,
          status: result.status,
          status_name: result.status_name,
          result_type: 1,
          result_section: "scripts",
          hardware_type: 0,
          physical_blockdevice: null,
          showing_results: old_result.showing_results,
          showing_menu: old_result.showing_menu,
          showing_history: old_result.showing_history,
          $selected: old_result.$selected
        }
      ]);
    });
  });

  it("_removeItem", function() {
    var node = makenode();
    var manager = NodeResultsManagerFactory.getManager(node, makeName("area"));
    var i;
    var result = {
      id: makeInteger(0, 100)
    };
    manager._items.push(result);
    angular.forEach(manager.commissioning_results, function(hw_type) {
      for (i = 0; i < 3; i++) {
        hw_type.results[makeName("subtext")] = [result];
      }
    });
    angular.forEach(manager.testing_results, function(hw_type) {
      for (i = 0; i < 3; i++) {
        hw_type.results[makeName("subtext")] = [result];
      }
    });
    manager.installation_results = [result];
    manager._removeItem(result);
    expect(manager._items).toEqual([]);
    angular.forEach(manager.commissioning_results, function(hw_type) {
      expect(hw_type.results).toEqual({});
    });
    angular.forEach(manager.testing_results, function(hw_type) {
      expect(hw_type.results).toEqual({});
    });
    expect(manager.installation_results).toEqual([]);
  });

  describe("_initBatchLoadParameters", function() {
    it("returns system_id when unknown area", function() {
      var node = makenode();
      var area = makeName("area");
      var manager = NodeResultsManagerFactory.getManager(node, area);
      expect(manager._initBatchLoadParameters()).toEqual({
        system_id: node.system_id
      });
    });

    it("returns system_id and summary area", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "summary");
      expect(manager._initBatchLoadParameters()).toEqual({
        system_id: node.system_id,
        has_surfaced: true,
        result_type: 2
      });
    });

    it("returns system_id and testing area", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "testing");
      expect(manager._initBatchLoadParameters()).toEqual({
        system_id: node.system_id,
        result_type: 2
      });
    });

    it("returns system_id and commissioning area", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "commissioning");
      expect(manager._initBatchLoadParameters()).toEqual({
        system_id: node.system_id,
        result_type: 0
      });
    });

    it("returns system_id and logs area", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node, "logs");
      expect(manager._initBatchLoadParameters()).toEqual({
        system_id: node.system_id,
        result_type: 1
      });
    });
  });

  describe("_getManager", function() {
    it("returns null when no manager with system_id exists", function() {
      expect(NodeResultsManagerFactory._getManager(0)).toBeNull();
    });

    it("returns object from _managers with system_id", function() {
      var node = makenode();
      var fakeManager = {
        _node: node
      };
      NodeResultsManagerFactory._managers.push(fakeManager);
      expect(NodeResultsManagerFactory._getManager(node)).toBe(fakeManager);
    });
  });

  describe("destroy", function() {
    it("calls _factory.destroyManager", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node);
      spyOn(NodeResultsManagerFactory, "destroyManager");
      manager.destroy();
      expect(NodeResultsManagerFactory.destroyManager).toHaveBeenCalledWith(
        manager
      );
    });

    it("calls clear on the RegionConnection if loaded", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node);
      spyOn(manager, "isLoaded").and.returnValue(true);
      spyOn(RegionConnection, "callMethod");
      manager.destroy();
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        manager._handler + ".clear",
        { system_id: node.system_id }
      );
    });
  });

  describe("getManager", function() {
    it("returns new manager with system_id doesnt exists", function() {
      var node = makenode();
      var area = pickItem(["testing", "commissioning", "summary", "logs"]);
      var manager = NodeResultsManagerFactory.getManager(node, area);
      expect(manager._node).toBe(node);
      expect(NodeResultsManagerFactory._managers).toEqual([manager]);
      if (area === "commissioning") {
        expect(manager.results).toBe(manager.commissioning_results);
      } else if (area === "logs") {
        expect(manager.results).toBe(manager.installation_results);
      } else {
        expect(manager.results).toBe(manager.testing_results);
      }
    });

    it("returns same manager with system_id exists", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node);
      expect(NodeResultsManagerFactory.getManager(node)).toBe(manager);
    });
  });

  describe("get_result_data", function() {
    it("calls NodeResultHandler.get_result_data", function(done) {
      var node = makenode();
      var output = makeName("output");
      var id = makeInteger(0, 100);
      var data_type = "output";
      webSocket.returnData.push(makeFakeResponse(output));
      const NodeResultsManager = NodeResultsManagerFactory.getManager(node);
      NodeResultsManager.get_result_data(id, data_type).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("noderesult.get_result_data");
        expect(sentObject.params.id).toEqual(id);
        expect(sentObject.params.data_type).toEqual(data_type);
        done();
      });
    });
  });

  describe("get_history", function() {
    it("calls NodeResultHandler.get_history", function(done) {
      var node = makenode();
      var output = [
        {
          id: makeInteger(0, 100),
          name: makeName("output"),
          status: makeInteger(0, 100)
        }
      ];
      var id = makeInteger(0, 100);
      webSocket.returnData.push(makeFakeResponse(output));
      const NodeResultsManager = NodeResultsManagerFactory.getManager(node);
      NodeResultsManager.get_history(id).then(function() {
        var sentObject = angular.fromJson(webSocket.sentData[0]);
        expect(sentObject.method).toBe("noderesult.get_history");
        expect(sentObject.params.id).toEqual(id);
        done();
      });
    });
  });

  describe("destroyManager", function() {
    it("removes manager from _managers", function() {
      var node = makenode();
      var manager = NodeResultsManagerFactory.getManager(node);
      NodeResultsManagerFactory.destroyManager(manager);
      expect(NodeResultsManagerFactory._managers).toEqual([]);
    });
  });
});
