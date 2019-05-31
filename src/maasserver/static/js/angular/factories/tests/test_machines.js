/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for MachinesManager.
 */

import { makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("MachinesManager", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

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
    expect(MachinesManager._batchSize).toBe(25);
  });

  it("set requires attributes", function() {
    expect(Object.keys(MachinesManager._metadataAttributes)).toEqual([
      "architecture",
      "status",
      "owner",
      "tags",
      "pod",
      "pool",
      "zone",
      "subnets",
      "fabrics",
      "spaces",
      "storage_tags",
      "release"
    ]);
  });

  describe("mountSpecialFilesystem", function() {
    it("calls mount_special", function() {
      spyOn(RegionConnection, "callMethod");
      var obj = {
        system_id: makeName("system-id"),
        fstype: makeName("fstype"),
        mount_point: makeName("/dir"),
        mount_options: makeName("options")
      };
      MachinesManager.mountSpecialFilesystem(obj);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "machine.mount_special",
        {
          system_id: obj.system_id,
          fstype: obj.fstype,
          mount_point: obj.mount_point,
          mount_options: obj.mount_options
        }
      );
    });
  });

  describe("unmountSpecialFilesystem", function() {
    it("calls unmount_special", function() {
      spyOn(RegionConnection, "callMethod");
      var machine = { system_id: makeName("system-id") };
      var mount_point = makeName("/dir");
      MachinesManager.unmountSpecialFilesystem(machine, mount_point);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "machine.unmount_special",
        {
          system_id: machine.system_id,
          mount_point: mount_point
        }
      );
    });
  });

  describe("applyStorageLayout", function() {
    it("calls apply_storage_layout", function() {
      spyOn(RegionConnection, "callMethod");
      var params = {
        system_id: makeName("system-id"),
        mount_point: makeName("/dir")
      };
      MachinesManager.applyStorageLayout(params);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "machine.apply_storage_layout",
        params
      );
    });
  });

  describe("createDatastore", function() {
    it("calls create_vmfs_datastore", function() {
      spyOn(RegionConnection, "callMethod");
      var params = {
        system_id: makeName("system-id"),
        block_devices: [1, 2, 3, 5],
        partitions: [5, 6, 7, 8],
        name: "New datastore"
      };
      MachinesManager.createDatastore(params);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "machine.create_vmfs_datastore",
        params
      );
    });
  });

  describe("updateDatastore", function() {
    it("calls update_vmfs_datastore", function() {
      spyOn(RegionConnection, "callMethod");
      var params = {
        system_id: makeName("system-id"),
        add_block_devices: [1, 2, 3, 4],
        add_partitions: [5, 6, 7, 8],
        remove_partitions: [],
        remove_block_devices: [],
        name: "New datastore",
        vmfs_datastore_id: 1
      };
      MachinesManager.updateDatastore(params);
      expect(RegionConnection.callMethod).toHaveBeenCalledWith(
        "machine.update_vmfs_datastore",
        params
      );
    });
  });
});
