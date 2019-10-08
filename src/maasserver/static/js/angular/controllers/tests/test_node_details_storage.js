/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeStorageController.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("removeAvailableByNew", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the removeAvailableByNew.
  var removeAvailableByNew;
  beforeEach(inject(function($filter) {
    removeAvailableByNew = $filter("removeAvailableByNew");
  }));

  it("returns disks if undefined availableNew", function() {
    var i,
      disk,
      disks = [];
    for (i = 0; i < 3; i++) {
      disk = {
        id: i
      };
      disks.push(disk);
    }
    expect(removeAvailableByNew(disks)).toBe(disks);
  });

  it("returns disks if undefined device(s) in availableNew", function() {
    var i,
      disk,
      disks = [];
    for (i = 0; i < 3; i++) {
      disk = {
        id: i
      };
      disks.push(disk);
    }
    var availableNew = {};
    expect(removeAvailableByNew(disks, availableNew)).toBe(disks);
  });

  it("removes availableNew.device from disks", function() {
    var i,
      disk,
      disks = [];
    for (i = 0; i < 3; i++) {
      disk = {
        id: i
      };
      disks.push(disk);
    }

    var availableNew = {
      device: disks[0]
    };
    var expectedDisks = angular.copy(disks);
    expectedDisks.splice(0, 1);

    expect(removeAvailableByNew(disks, availableNew)).toEqual(expectedDisks);
  });

  it("removes availableNew.devices from disks", function() {
    var i,
      disk,
      disks = [];
    for (i = 0; i < 6; i++) {
      disk = {
        id: i
      };
      disks.push(disk);
    }

    var availableNew = {
      devices: [disks[0], disks[1]]
    };
    var expectedDisks = angular.copy(disks);
    expectedDisks.splice(0, 2);

    expect(removeAvailableByNew(disks, availableNew)).toEqual(expectedDisks);
  });
});

describe("NodeStorageController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $parentScope, $scope, $q;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $parentScope = $rootScope.$new();
    $scope = $parentScope.$new();
    $q = $injector.get("$q");
  }));

  // Load the required dependencies for the NodeStorageController.
  var MachinesManager;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
  }));

  // Create the node and functions that will be called on the parent.
  var node, updateNodeSpy, canEditSpy;
  beforeEach(function() {
    node = {
      system_id: makeName("system_id"),
      architecture: "amd64/generic",
      disks: []
    };
    updateNodeSpy = jasmine.createSpy("updateNode");
    canEditSpy = jasmine.createSpy("canEdit");
    $parentScope.node = node;
    $parentScope.updateNode = updateNodeSpy;
    $parentScope.canEdit = canEditSpy;
    $parentScope.controllerLoaded = jasmine.createSpy("controllerLoaded");
  });

  // Makes the NodeStorageController
  function makeController() {
    // Create the controller.
    var controller = $controller("NodeStorageController", {
      $scope: $scope,
      MachinesManager: MachinesManager
    });
    return controller;
  }

  // Return a known set of disks for testing the loading of disks
  // into the controller.
  function makeDisks() {
    return [
      {
        // Blank disk
        id: 0,
        is_boot: true,
        name: makeName("name"),
        model: makeName("model"),
        serial: makeName("serial"),
        tags: [],
        type: makeName("type"),
        size: Math.pow(1024, 4),
        size_human: "1024 GB",
        available_size: Math.pow(1024, 4),
        available_size_human: "1024 GB",
        used_size: 0,
        used_size_human: "0.0 Bytes",
        partition_table_type: makeName("partition_table_type"),
        used_for: "Unused",
        filesystem: null,
        partitions: null,
        test_status: 0,
        firmware_version: makeName("firmware_version")
      },
      {
        // Disk with filesystem, no mount point
        id: 1,
        is_boot: false,
        name: makeName("name"),
        model: makeName("model"),
        serial: makeName("serial"),
        tags: [],
        type: makeName("type"),
        size: Math.pow(1024, 4),
        size_human: "1024 GB",
        available_size: 0,
        available_size_human: "0 GB",
        used_size: Math.pow(1024, 4),
        used_size_human: "1024 GB",
        partition_table_type: makeName("partition_table_type"),
        used_for: "Unmounted ext4 formatted filesystem.",
        filesystem: {
          id: 0,
          is_format_fstype: true,
          fstype: "ext4",
          mount_point: null,
          mount_options: null
        },
        partitions: null,
        test_status: 1,
        firmware_version: makeName("firmware_version")
      },
      {
        // Disk with mounted filesystem
        id: 2,
        is_boot: false,
        name: makeName("name"),
        model: makeName("model"),
        serial: makeName("serial"),
        tags: [],
        type: makeName("type"),
        size: Math.pow(1024, 4),
        size_human: "1024 GB",
        available_size: 0,
        available_size_human: "0 GB",
        used_size: Math.pow(1024, 4),
        used_size_human: "1024 GB",
        partition_table_type: makeName("partition_table_type"),
        used_for: "ext4 formatted filesystem mounted at /.",
        filesystem: {
          id: 1,
          is_format_fstype: true,
          fstype: "ext4",
          mount_point: "/",
          mount_options: makeName("options")
        },
        partitions: null,
        test_status: 2,
        firmware_version: makeName("firmware_version")
      },
      {
        // Partitioned disk, one partition free one used
        id: 3,
        is_boot: false,
        name: makeName("name"),
        model: makeName("model"),
        serial: makeName("serial"),
        tags: [],
        type: makeName("type"),
        size: Math.pow(1024, 4),
        size_human: "1024 GB",
        available_size: 0,
        available_size_human: "0 GB",
        used_size: Math.pow(1024, 4),
        used_size_human: "1024 GB",
        partition_table_type: "GPT",
        filesystem: null,
        partitions: [
          {
            id: 0,
            name: makeName("partition_name"),
            size_human: "512 GB",
            type: "partition",
            filesystem: null,
            used_for: "Unused"
          },
          {
            id: 1,
            name: makeName("partition_name"),
            size_human: "512 GB",
            type: "partition",
            filesystem: {
              id: 2,
              is_format_fstype: true,
              fstype: "ext4",
              mount_point: "/mnt",
              mount_options: makeName("options")
            },
            used_for: "ext4 formatted filesystem mounted at /mnt."
          }
        ],
        test_status: 3,
        firmware_version: makeName("firmware_version")
      },
      {
        // Disk that is a cache set.
        id: 4,
        is_boot: false,
        name: "cache0",
        model: "",
        serial: "",
        tags: [],
        type: "cache-set",
        size: Math.pow(1024, 4),
        size_human: "1024 GB",
        available_size: 0,
        available_size_human: "0 GB",
        used_size: Math.pow(1024, 4),
        used_size_human: "1024 GB",
        partition_table_type: null,
        used_for: "",
        filesystem: null,
        partitions: null,
        test_status: 4,
        firmware_version: makeName("firmware_version")
      }
    ];
  }

  it("sets initial values", function() {
    makeController();
    expect($scope.tableInfo.column).toBe("name");
    expect($scope.has_disks).toBe(false);
    expect($scope.filesystems).toEqual([]);
    expect($scope.filesystemsMap).toEqual({});
    expect($scope.filesystemMode).toBeNull();
    expect($scope.filesystemAllSelected).toBe(false);
    expect($scope.available).toEqual([]);
    expect($scope.availableMap).toEqual({});
    expect($scope.availableMode).toBeNull();
    expect($scope.availableAllSelected).toBe(false);
    expect($scope.cachesets).toEqual([]);
    expect($scope.cachesetsMap).toEqual({});
    expect($scope.cachesetsMode).toBeNull();
    expect($scope.cachesetsAllSelected).toBe(false);
    expect($scope.used).toEqual([]);
  });

  it("starts watching disks once nodeLoaded called", function() {
    makeController();

    spyOn($scope, "$watch");
    $scope.nodeLoaded();

    var watches = [];
    var i,
      calls = $scope.$watch.calls.allArgs();
    for (i = 0; i < calls.length; i++) {
      watches.push(calls[i][0]);
    }

    expect(watches).toEqual(["node.disks"]);
  });

  it("disks updated once nodeLoaded called", function() {
    var disks = makeDisks();
    node.disks = disks;

    var filesystems = [
      {
        type: "filesystem",
        name: disks[2].name,
        size_human: disks[2].size_human,
        fstype: disks[2].filesystem.fstype,
        mount_point: disks[2].filesystem.mount_point,
        mount_options: disks[2].filesystem.mount_options,
        block_id: disks[2].id,
        partition_id: null,
        filesystem_id: disks[2].filesystem.id,
        original_type: disks[2].type,
        original: disks[2],
        $selected: false
      },
      {
        type: "filesystem",
        name: disks[3].partitions[1].name,
        size_human: disks[3].partitions[1].size_human,
        fstype: disks[3].partitions[1].filesystem.fstype,
        mount_point: disks[3].partitions[1].filesystem.mount_point,
        mount_options: disks[3].partitions[1].filesystem.mount_options,
        block_id: disks[3].id,
        partition_id: disks[3].partitions[1].id,
        filesystem_id: disks[3].partitions[1].filesystem.id,
        original_type: "partition",
        original: disks[3].partitions[1],
        $selected: false
      }
    ];
    var cachesets = [
      {
        type: "cache-set",
        name: disks[4].name,
        size_human: disks[4].size_human,
        cache_set_id: disks[4].id,
        used_by: disks[4].used_for,
        $selected: false
      }
    ];
    var available = [
      {
        name: disks[0].name,
        is_boot: disks[0].is_boot,
        size_human: disks[0].size_human,
        size: disks[0].size,
        available_size_human: disks[0].available_size_human,
        used_size_human: disks[0].used_size_human,
        type: disks[0].type,
        model: disks[0].model,
        serial: disks[0].serial,
        tags: disks[0].tags,
        fstype: null,
        mount_point: null,
        mount_options: null,
        block_id: 0,
        partition_id: null,
        has_partitions: false,
        original: disks[0],
        test_status: disks[0].test_status,
        firmware_version: disks[0].firmware_version,
        $selected: false,
        $options: {}
      },
      {
        name: disks[1].name,
        is_boot: disks[1].is_boot,
        size_human: disks[1].size_human,
        size: disks[1].size,
        available_size_human: disks[1].available_size_human,
        used_size_human: disks[1].used_size_human,
        type: disks[1].type,
        model: disks[1].model,
        serial: disks[1].serial,
        tags: disks[1].tags,
        fstype: "ext4",
        mount_point: null,
        mount_options: null,
        block_id: 1,
        partition_id: null,
        has_partitions: false,
        original: disks[1],
        test_status: disks[1].test_status,
        firmware_version: disks[1].firmware_version,
        $selected: false,
        $options: {}
      },
      {
        name: disks[3].partitions[0].name,
        is_boot: false,
        size_human: disks[3].partitions[0].size_human,
        size: disks[3].partitions[0].size,
        available_size_human: disks[3].partitions[0].available_size_human,
        used_size_human: disks[3].partitions[0].used_size_human,
        type: disks[3].partitions[0].type,
        model: "",
        serial: "",
        tags: [],
        fstype: null,
        mount_point: null,
        mount_options: null,
        block_id: 3,
        partition_id: 0,
        has_partitions: false,
        original: disks[3].partitions[0],
        $selected: false,
        $options: {}
      }
    ];
    var used = [
      {
        name: disks[2].name,
        is_boot: disks[2].is_boot,
        type: disks[2].type,
        model: disks[2].model,
        serial: disks[2].serial,
        size_human: disks[2].size_human,
        tags: disks[2].tags,
        used_for: disks[2].used_for,
        has_partitions: false,
        test_status: disks[2].test_status,
        firmware_version: disks[2].firmware_version
      },
      {
        name: disks[3].name,
        is_boot: disks[3].is_boot,
        type: disks[3].type,
        model: disks[3].model,
        serial: disks[3].serial,
        size_human: disks[3].size_human,
        tags: disks[3].tags,
        used_for: disks[3].used_for,
        has_partitions: true,
        test_status: disks[3].test_status,
        firmware_version: disks[3].firmware_version
      },
      {
        name: disks[3].partitions[1].name,
        is_boot: false,
        type: "partition",
        model: "",
        serial: "",
        size_human: disks[3].partitions[1].size_human,
        tags: [],
        used_for: disks[3].partitions[1].used_for
      }
    ];
    makeController();
    $scope.nodeLoaded();
    $rootScope.$digest();
    expect($scope.has_disks).toEqual(true);
    expect($scope.filesystems).toEqual(filesystems);
    expect($scope.cachesets).toEqual(cachesets);
    expect($scope.available).toEqual(available);
    expect($scope.used).toEqual(used);
  });

  it("disks $selected and $options not lost on update", function() {
    makeController();
    var disks = makeDisks();
    node.disks = disks;

    // Load the filesystems, cachesets, available, and used once.
    $scope.nodeLoaded();
    $rootScope.$digest();

    // Set all filesystems, cachesets, and available to selected.
    angular.forEach($scope.filesystems, function(filesystem) {
      filesystem.$selected = true;
    });
    angular.forEach($scope.cachesets, function(cacheset) {
      cacheset.$selected = true;
    });
    angular.forEach($scope.available, function(disk) {
      disk.$selected = true;
    });

    // Get all the options for available.
    var options = [];
    angular.forEach($scope.available, function(disk) {
      options.push(disk.$options);
    });

    // Force the disks to change so the filesystems, cachesets, available,
    // and used are reloaded.
    var firstFilesystem = $scope.filesystems[0];
    node.disks = angular.copy(node.disks);
    $rootScope.$digest();
    expect($scope.filesystems[0]).not.toBe(firstFilesystem);
    expect($scope.filesystems[0]).toEqual(firstFilesystem);

    // All filesystems, cachesets and available should be selected.
    angular.forEach($scope.filesystems, function(filesystem) {
      expect(filesystem.$selected).toBe(true);
    });
    angular.forEach($scope.cachesets, function(cacheset) {
      expect(cacheset.$selected).toBe(true);
    });
    angular.forEach($scope.available, function(disk) {
      expect(disk.$selected).toBe(true);
    });

    // All available should have the same options.
    angular.forEach($scope.available, function(disk, idx) {
      expect(disk.$options).toBe(options[idx]);
    });
  });

  it("availableNew.device object is updated", function() {
    makeController();
    var disks = makeDisks();
    node.disks = disks;

    // Load the filesystems, cachesets, available, and used once.
    $scope.nodeLoaded();
    $rootScope.$digest();

    // Set availableNew.device to a disk from available.
    var disk = $scope.available[0];
    $scope.availableNew.device = disk;

    // Force the update. The device should be the same value but
    // a new object.
    node.disks = angular.copy(node.disks);
    $rootScope.$digest();
    expect($scope.availableNew.device).toEqual(disk);
    expect($scope.availableNew.device).not.toBe(disk);
  });

  it("availableNew.devices array is updated", function() {
    makeController();
    var disks = makeDisks();
    node.disks = disks;

    // Load the filesystems, cachesets, available, and used once.
    $scope.nodeLoaded();
    $rootScope.$digest();

    // Set availableNew.device to a disk from available.
    var disk0 = $scope.available[0];
    var disk1 = $scope.available[1];
    $scope.availableNew.devices = [disk0, disk1];

    // Force the update. The devices should be the same values but
    // a new objects.
    node.disks = angular.copy(node.disks);
    $rootScope.$digest();
    expect($scope.availableNew.devices[0]).toEqual(disk0);
    expect($scope.availableNew.devices[0]).not.toBe(disk0);
    expect($scope.availableNew.devices[1]).toEqual(disk1);
    expect($scope.availableNew.devices[1]).not.toBe(disk1);
  });

  describe("isBootDiskDisabled", function() {
    it("returns true when not editable", function() {
      makeController();
      $scope.canEdit = function() {
        return false;
      };
      $scope.node.status = "Ready";
      var disk = { type: "physical" };

      expect($scope.isBootDiskDisabled(disk, "available")).toBe(true);
    });

    it("returns true when not node not ready", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Deploying";
      var disk = { type: "physical" };

      expect($scope.isBootDiskDisabled(disk, "available")).toBe(true);
    });

    it("returns true if not physical", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Ready";
      var disk = { type: "virtual" };

      expect($scope.isBootDiskDisabled(disk, "available")).toBe(true);
    });

    it("returns false if in available", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Ready";
      var disk = { type: "physical" };

      expect($scope.isBootDiskDisabled(disk, "available")).toBe(false);
    });

    it("returns true when used and no partitions", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Ready";
      var disk = { type: "physical", has_partitions: false };

      expect($scope.isBootDiskDisabled(disk, "used")).toBe(true);
    });

    it("returns false when ready, used and partitions", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Ready";
      var disk = { type: "physical", has_partitions: true };

      expect($scope.isBootDiskDisabled(disk, "used")).toBe(false);
    });

    it("returns false when allocated, used and partitions", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      $scope.node.status = "Allocated";
      var disk = { type: "physical", has_partitions: true };

      expect($scope.isBootDiskDisabled(disk, "used")).toBe(false);
    });
  });

  describe("setAsBootDisk", function() {
    it("does nothing if already boot disk", function() {
      makeController();
      var disk = { is_boot: true };
      spyOn(MachinesManager, "setBootDisk");
      spyOn($scope, "isBootDiskDisabled").and.returnValue(false);

      $scope.setAsBootDisk(disk);

      expect(MachinesManager.setBootDisk).not.toHaveBeenCalled();
    });

    it("does nothing if set boot disk disabled", function() {
      makeController();
      var disk = { is_boot: false };
      spyOn(MachinesManager, "setBootDisk");
      spyOn($scope, "isBootDiskDisabled").and.returnValue(true);

      $scope.setAsBootDisk(disk);

      expect(MachinesManager.setBootDisk).not.toHaveBeenCalled();
    });

    it("calls MachinesManager.setBootDisk", function() {
      makeController();
      var disk = { block_id: makeInteger(0, 100), is_boot: false };
      spyOn(MachinesManager, "setBootDisk");
      spyOn($scope, "isBootDiskDisabled").and.returnValue(false);

      $scope.setAsBootDisk(disk);

      expect(MachinesManager.setBootDisk).toHaveBeenCalledWith(
        node,
        disk.block_id
      );
    });
  });

  describe("getSelectedFilesystems", function() {
    it("returns selected filesystems", function() {
      makeController();
      var filesystems = [
        { $selected: true },
        { $selected: true },
        { $selected: false },
        { $selected: false }
      ];
      $scope.filesystems = filesystems;
      expect($scope.getSelectedFilesystems()).toEqual([
        filesystems[0],
        filesystems[1]
      ]);
    });
  });

  describe("updateFilesystemSelection", function() {
    it("sets filesystemMode to NONE when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([]);
      $scope.filesystemMode = "other";

      $scope.updateFilesystemSelection();

      expect($scope.filesystemMode).toBeNull();
    });

    it("doesn't sets filesystemMode to SINGLE when not force", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
      $scope.filesystemMode = "other";

      $scope.updateFilesystemSelection();

      expect($scope.filesystemMode).toBe("other");
    });

    it("sets filesystemMode to SINGLE when force", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
      $scope.filesystemMode = "other";

      $scope.updateFilesystemSelection(true);

      expect($scope.filesystemMode).toBe("single");
    });

    it("doesn't sets filesystemMode to MUTLI when not force", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}, {}]);
      $scope.filesystemMode = "other";

      $scope.updateFilesystemSelection();

      expect($scope.filesystemMode).toBe("other");
    });

    it("sets filesystemMode to MULTI when force", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}, {}]);
      $scope.filesystemMode = "other";

      $scope.updateFilesystemSelection(true);

      expect($scope.filesystemMode).toBe("multi");
    });

    it("sets filesystemAllSelected to false when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedFilesystems").and.returnValue([]);
      $scope.filesystemAllSelected = true;

      $scope.updateFilesystemSelection();

      expect($scope.filesystemAllSelected).toBe(false);
    });

    it("sets filesystemAllSelected to false when not all selected", function() {
      makeController();
      $scope.filesystems = [{}, {}];
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
      $scope.filesystemAllSelected = true;

      $scope.updateFilesystemSelection();

      expect($scope.filesystemAllSelected).toBe(false);
    });

    it("sets filesystemAllSelected to true when all selected", function() {
      makeController();
      $scope.filesystems = [{}, {}];
      spyOn($scope, "getSelectedFilesystems").and.returnValue([{}, {}]);
      $scope.filesystemAllSelected = false;

      $scope.updateFilesystemSelection();

      expect($scope.filesystemAllSelected).toBe(true);
    });
  });

  describe("toggleFilesystemSelect", function() {
    it("inverts $selected", function() {
      makeController();
      var filesystem = { $selected: true };
      spyOn($scope, "updateFilesystemSelection");

      $scope.toggleFilesystemSelect(filesystem);

      expect(filesystem.$selected).toBe(false);
      $scope.toggleFilesystemSelect(filesystem);
      expect(filesystem.$selected).toBe(true);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("toggleFilesystemAllSelect", function() {
    it("sets all to true if not all selected", function() {
      makeController();
      var filesystems = [{ $selected: true }, { $selected: false }];
      $scope.filesystems = filesystems;
      $scope.filesystemAllSelected = false;
      spyOn($scope, "updateFilesystemSelection");

      $scope.toggleFilesystemAllSelect();

      expect(filesystems[0].$selected).toBe(true);
      expect(filesystems[1].$selected).toBe(true);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
    });

    it("sets all to false if all selected", function() {
      makeController();
      var filesystems = [{ $selected: true }, { $selected: true }];
      $scope.filesystems = filesystems;
      $scope.filesystemAllSelected = true;
      spyOn($scope, "updateFilesystemSelection");

      $scope.toggleFilesystemAllSelect();

      expect(filesystems[0].$selected).toBe(false);
      expect(filesystems[1].$selected).toBe(false);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("isFilesystemsDisabled", function() {
    it("returns false for NONE", function() {
      makeController();
      $scope.filesystemMode = null;
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isFilesystemsDisabled()).toBe(false);
    });

    it("returns false for SINGLE", function() {
      makeController();
      $scope.filesystemMode = "single";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isFilesystemsDisabled()).toBe(false);
    });

    it("returns false for MULTI", function() {
      makeController();
      $scope.filesystemMode = "multi";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isFilesystemsDisabled()).toBe(false);
    });

    it("returns true for UNMOUNT", function() {
      makeController();
      $scope.filesystemMode = "unmount";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isFilesystemsDisabled()).toBe(true);
    });

    it("returns true when isAllStorageDisabled", function() {
      makeController();
      $scope.filesystemMode = "multi";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);

      expect($scope.isFilesystemsDisabled()).toBe(true);
    });
  });

  describe("filesystemCancel", function() {
    it("calls updateFilesystemSelection with force true", function() {
      makeController();
      var filesystems = [{ $selected: true }, { $selected: false }];
      $scope.filesystems = filesystems;
      spyOn($scope, "updateFilesystemSelection");

      $scope.filesystemCancel();

      expect(filesystems[0].$selected).toBe(false);
      expect(filesystems[1].$selected).toBe(false);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("filesystemUnmount", function() {
    it("sets filesystemMode to UNMOUNT", function() {
      makeController();
      $scope.filesystemMode = "other";

      $scope.filesystemUnmount();

      expect($scope.filesystemMode).toBe("unmount");
    });
  });

  describe("quickFilesystemUnmount", function() {
    it("selects filesystem and calls filesystemUnmount", function() {
      makeController();
      var filesystems = [{ $selected: true }, { $selected: false }];
      $scope.filesystems = filesystems;
      spyOn($scope, "updateFilesystemSelection");
      spyOn($scope, "filesystemUnmount");

      $scope.quickFilesystemUnmount(filesystems[1]);

      expect(filesystems[0].$selected).toBe(false);
      expect(filesystems[1].$selected).toBe(true);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
      expect($scope.filesystemUnmount).toHaveBeenCalled();
    });
  });

  describe("filesystemConfirmUnmount", function() {
    it("calls MachinesManager.updateFilesystem", function() {
      makeController();
      var filesystem = {
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        fstype: makeName("fs")
      };
      $scope.filesystems = [filesystem];
      spyOn(MachinesManager, "updateFilesystem");
      spyOn($scope, "updateFilesystemSelection");

      $scope.filesystemConfirmUnmount(filesystem);

      expect(MachinesManager.updateFilesystem).toHaveBeenCalledWith(
        node,
        filesystem.block_id,
        filesystem.partition_id,
        filesystem.fstype,
        null,
        null
      );
    });

    it("removes filesystem from filesystems", function() {
      makeController();
      var filesystem = {
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        fstype: makeName("fs")
      };
      $scope.filesystems = [filesystem];
      spyOn(MachinesManager, "updateFilesystem");
      spyOn($scope, "updateFilesystemSelection");

      $scope.filesystemConfirmUnmount(filesystem);

      expect($scope.filesystems).toEqual([]);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith();
    });
  });

  describe("filesystemDelete", function() {
    it("sets filesystemMode to DELETE", function() {
      makeController();
      $scope.filesystemMode = "other";

      $scope.filesystemDelete();

      expect($scope.filesystemMode).toBe("delete");
    });
  });

  describe("quickFilesystemDelete", function() {
    it("selects filesystem and calls filesystemDelete", function() {
      makeController();
      var filesystems = [{ $selected: true }, { $selected: false }];
      $scope.filesystems = filesystems;
      spyOn($scope, "updateFilesystemSelection");
      spyOn($scope, "filesystemDelete");

      $scope.quickFilesystemDelete(filesystems[1]);

      expect(filesystems[0].$selected).toBe(false);
      expect(filesystems[1].$selected).toBe(true);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(true);
      expect($scope.filesystemDelete).toHaveBeenCalled();
    });
  });

  describe("filesystemConfirmDelete", function() {
    it("calls MachinesManager.deletePartition for partition", function() {
      makeController();
      var filesystem = {
        original_type: "partition",
        original: {
          id: makeInteger(0, 100)
        }
      };
      $scope.filesystems = [filesystem];
      spyOn(MachinesManager, "deletePartition");
      spyOn($scope, "updateFilesystemSelection");

      $scope.filesystemConfirmDelete(filesystem);
      expect(MachinesManager.deletePartition).toHaveBeenCalledWith(
        node,
        filesystem.original.id
      );
      expect($scope.filesystems).toEqual([]);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith();
    });

    it("calls MachinesManager.deleteFilesystem for disk", function() {
      makeController();
      var filesystem = {
        original_type: "physical",
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        filesystem_id: makeInteger(0, 100)
      };
      $scope.filesystems = [filesystem];
      spyOn(MachinesManager, "deleteFilesystem");
      spyOn($scope, "updateFilesystemSelection");

      $scope.filesystemConfirmDelete(filesystem);
      expect(MachinesManager.deleteFilesystem).toHaveBeenCalledWith(
        node,
        filesystem.block_id,
        filesystem.partition_id,
        filesystem.filesystem_id
      );
      expect($scope.filesystems).toEqual([]);
      expect($scope.updateFilesystemSelection).toHaveBeenCalledWith();
    });
  });

  describe("hasUnmountedFilesystem", function() {
    it("returns false if no fstype", function() {
      makeController();
      var disk = {
        fstype: null
      };

      expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
    });

    it("returns false if empty fstype", function() {
      makeController();
      var disk = {
        fstype: ""
      };

      expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
    });

    it("returns true if no mount_point", function() {
      makeController();
      var disk = {
        fstype: "ext4",
        mount_point: null
      };

      expect($scope.hasUnmountedFilesystem(disk)).toBe(true);
    });

    it("returns true if empty mount_point", function() {
      makeController();
      var disk = {
        fstype: "ext4",
        mount_point: ""
      };

      expect($scope.hasUnmountedFilesystem(disk)).toBe(true);
    });

    it("returns false if has mount_point", function() {
      makeController();
      var disk = {
        fstype: "ext4",
        mount_point: "/"
      };

      expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
    });
  });

  describe("showFreeSpace", function() {
    it("returns true if volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg"
      };

      expect($scope.showFreeSpace(disk)).toBe(true);
    });

    it("returns true if physical with partitions", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: true
      };

      expect($scope.showFreeSpace(disk)).toBe(true);
    });

    it("returns false if physical without partitions", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: false
      };

      expect($scope.showFreeSpace(disk)).toBe(false);
    });

    it("returns true if virtual with partitions", function() {
      makeController();
      var disk = {
        type: "virtual",
        has_partitions: true
      };

      expect($scope.showFreeSpace(disk)).toBe(true);
    });

    it("returns false if virtual without partitions", function() {
      makeController();
      var disk = {
        type: "virtual",
        has_partitions: false
      };

      expect($scope.showFreeSpace(disk)).toBe(false);
    });

    it("returns false otherwise", function() {
      makeController();
      var disk = {
        type: "other"
      };

      expect($scope.showFreeSpace(disk)).toBe(false);
    });
  });

  describe("getDeviceType", function() {
    it("returns logical volume", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "lvm-vg"
      };

      expect($scope.getDeviceType(disk)).toBe("Logical volume");
    });

    it("returns raid", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "raid-5"
      };

      expect($scope.getDeviceType(disk)).toBe("RAID 5");
    });

    it("returns parent_type", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "other"
      };

      expect($scope.getDeviceType(disk)).toBe("Other");
    });

    it("returns volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg"
      };

      expect($scope.getDeviceType(disk)).toBe("Volume group");
    });

    it("returns type", function() {
      makeController();
      var disk = {
        type: "physical"
      };

      expect($scope.getDeviceType(disk)).toBe("Physical");
    });
  });

  describe("getDeviceTypeLower", function() {
    it("returns logical volume", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "lvm-vg"
      };

      expect($scope.getDeviceTypeLower(disk)).toBe("logical volume");
    });

    it("returns raid", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "raid-5"
      };

      expect($scope.getDeviceTypeLower(disk)).toBe("raid 5");
    });

    it("returns parent_type", function() {
      makeController();
      var disk = {
        type: "virtual",
        parent_type: "other"
      };

      expect($scope.getDeviceTypeLower(disk)).toBe("other");
    });

    it("returns volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg"
      };

      expect($scope.getDeviceTypeLower(disk)).toBe("volume group");
    });

    it("returns type", function() {
      makeController();
      var disk = {
        type: "physical"
      };

      expect($scope.getDeviceTypeLower(disk)).toBe("physical");
    });
  });

  describe("getSelectedAvailable", function() {
    it("returns selected available", function() {
      makeController();
      var available = [
        { $selected: true },
        { $selected: true },
        { $selected: false },
        { $selected: false }
      ];
      $scope.available = available;
      expect($scope.getSelectedAvailable()).toEqual([
        available[0],
        available[1]
      ]);
    });
  });

  describe("updateAvailableSelection", function() {
    it("sets availableMode to NONE when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([]);
      $scope.availableMode = "other";

      $scope.updateAvailableSelection();

      expect($scope.availableMode).toBeNull();
    });

    it("doesn't sets availableMode to SINGLE when not force", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      $scope.availableMode = "other";

      $scope.updateAvailableSelection();

      expect($scope.availableMode).toBe("other");
    });

    it("sets availableMode to SINGLE when force", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      $scope.availableMode = "other";

      $scope.updateAvailableSelection(true);

      expect($scope.availableMode).toBe("single");
    });

    it("doesn't sets availableMode to MUTLI when not force", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      $scope.availableMode = "other";

      $scope.updateAvailableSelection();

      expect($scope.availableMode).toBe("other");
    });

    it("sets availableMode to MULTI when force", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      $scope.availableMode = "other";

      $scope.updateAvailableSelection(true);

      expect($scope.availableMode).toBe("multi");
    });

    it("sets availableAllSelected to false when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([]);
      $scope.availableAllSelected = true;

      $scope.updateAvailableSelection();

      expect($scope.availableAllSelected).toBe(false);
    });

    it("sets availableAllSelected to false when not all selected", function() {
      makeController();
      $scope.available = [{}, {}];
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      $scope.availableAllSelected = true;

      $scope.updateAvailableSelection();

      expect($scope.availableAllSelected).toBe(false);
    });

    it("sets availableAllSelected to true when all selected", function() {
      makeController();
      $scope.available = [{}, {}];
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      $scope.availableAllSelected = false;

      $scope.updateAvailableSelection();

      expect($scope.availableAllSelected).toBe(true);
    });
  });

  describe("toggleAvailableSelect", function() {
    it("inverts $selected", function() {
      makeController();
      var disk = { $selected: true };
      spyOn($scope, "updateAvailableSelection");

      $scope.toggleAvailableSelect(disk);

      expect(disk.$selected).toBe(false);
      $scope.toggleAvailableSelect(disk);
      expect(disk.$selected).toBe(true);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("toggleAvailableAllSelect", function() {
    it("sets all to true if not all selected", function() {
      makeController();
      var available = [{ $selected: true }, { $selected: false }];
      $scope.available = available;
      $scope.availableAllSelected = false;
      spyOn($scope, "updateAvailableSelection");

      $scope.toggleAvailableAllSelect();

      expect(available[0].$selected).toBe(true);
      expect(available[1].$selected).toBe(true);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("sets all to false if all selected", function() {
      makeController();
      var available = [{ $selected: true }, { $selected: true }];
      $scope.available = available;
      $scope.availableAllSelected = true;
      spyOn($scope, "updateAvailableSelection");

      $scope.toggleAvailableAllSelect();

      expect(available[0].$selected).toBe(false);
      expect(available[1].$selected).toBe(false);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("isAvailableDisabled", function() {
    it("returns false for NONE", function() {
      makeController();
      $scope.availableMode = null;
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isAvailableDisabled()).toBe(false);
    });

    it("returns false for SINGLE", function() {
      makeController();
      $scope.availableMode = "single";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isAvailableDisabled()).toBe(false);
    });

    it("returns false for MULTI", function() {
      makeController();
      $scope.availableMode = "multi";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isAvailableDisabled()).toBe(false);
    });

    it("returns true for UNMOUNT", function() {
      makeController();
      $scope.availableMode = "unmount";
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isAvailableDisabled()).toBe(true);
    });
  });

  describe("canFormatAndMount", function() {
    it("returns false if lvm-vg", function() {
      makeController();
      var disk = { type: "lvm-vg" };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      expect($scope.canFormatAndMount(disk)).toBe(false);
    });

    it("returns false if has_partitions", function() {
      makeController();
      var disk = { type: "physical", has_partitions: true };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      expect($scope.canFormatAndMount(disk)).toBe(false);
    });

    it("returns false if physical and is boot disk", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: false,
        original: {
          is_boot: true
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      expect($scope.canFormatAndMount(disk)).toBe(false);
    });

    it("returns true otherwise", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: false,
        original: {
          is_boot: false
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      expect($scope.canFormatAndMount(disk)).toBe(true);
    });
  });

  describe("getPartitionButtonText", function() {
    it("returns Add Partition if already has partitions", function() {
      makeController();
      expect(
        $scope.getPartitionButtonText({
          has_partitions: true
        })
      ).toBe("Add partition");
    });

    it("returns Partition if no partitions", function() {
      makeController();
      expect(
        $scope.getPartitionButtonText({
          has_partitions: false
        })
      ).toBe("Partition");
    });
  });

  describe("canAddPartition", function() {
    it("returns false if partition", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect(
        $scope.canAddPartition({
          type: "partition"
        })
      ).toBe(false);
    });

    it("returns false if lvm-vg", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect(
        $scope.canAddPartition({
          type: "lvm-vg"
        })
      ).toBe(false);
    });

    it("returns false if logical volume", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect(
        $scope.canAddPartition({
          type: "virtual",
          parent_type: "lvm-vg"
        })
      ).toBe(false);
    });

    it("returns false if bcache", function() {
      makeController();
      $scope.canEdit = function() {
        return true;
      };
      expect(
        $scope.canAddPartition({
          type: "virtual",
          parent_type: "bcache"
        })
      ).toBe(false);
    });

    it("returns false if formatted", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect(
        $scope.canAddPartition({
          type: "physical",
          fstype: "ext4"
        })
      ).toBe(false);
    });

    it(
      "returns false if available_size is less than partition size " +
        "and partition table extra space",
      function() {
        makeController();
        var disk = {
          type: "physical",
          fstype: "",
          original: {
            partition_table_type: null,
            available_size: 2.5 * 1024 * 1024,
            block_size: 1024
          }
        };
        spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
        $scope.canEdit = function() {
          return true;
        };
        expect($scope.canAddPartition(disk)).toBe(false);
      }
    );

    it(`returns false if available_size is
        less than partition size`, function() {
      makeController();
      var disk = {
        type: "physical",
        fstype: "",
        original: {
          partition_table_type: "mbr",
          available_size: 1024 * 1024,
          block_size: 1024
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canAddPartition(disk)).toBe(false);
    });

    it(
      "returns false if available_size is less than partition size " +
        "when node is ppc64el architecture",
      function() {
        makeController();
        var disk = {
          type: "physical",
          fstype: "",
          original: {
            partition_table_type: null,
            available_size: 2.5 * 1024 * 1024 + 8 * 1024 * 1024,
            block_size: 1024
          }
        };
        node.architecture = "ppc64el/generic";
        spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
        $scope.canEdit = function() {
          return true;
        };
        expect($scope.canAddPartition(disk)).toBe(false);
      }
    );

    it("returns false if not super user", function() {
      makeController();
      var disk = {
        type: "physical",
        fstype: "",
        original: {
          partition_table_type: null,
          available_size: 10 * 1024 * 1024,
          block_size: 1024
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return false;
      };
      expect($scope.canAddPartition(disk)).toBe(false);
    });

    it("returns false if isAllStorageDisabled", function() {
      makeController();
      var disk = {
        type: "physical",
        fstype: "",
        original: {
          partition_table_type: null,
          available_size: 10 * 1024 * 1024,
          block_size: 1024
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canAddPartition(disk)).toBe(false);
    });

    it("returns true otherwise", function() {
      makeController();
      var disk = {
        type: "physical",
        fstype: "",
        original: {
          partition_table_type: null,
          available_size: 10 * 1024 * 1024,
          block_size: 1024
        }
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canAddPartition(disk)).toBe(true);
    });
  });

  describe("isNameInvalid", function() {
    it("returns false if name is blank", function() {
      makeController();
      var disk = {
        name: ""
      };

      expect($scope.isNameInvalid(disk)).toBe(false);
    });

    it("returns true if name is already used by another disk", function() {
      makeController();
      var otherId = makeInteger(0, 100);
      var id = makeInteger(100, 200);
      var name = makeName("name");
      var otherDisk = {
        id: otherId,
        type: "physical",
        name: name
      };
      var thisDisk = {
        id: id,
        type: "physical",
        name: name
      };

      $scope.node.disks = [otherDisk, thisDisk];
      var disk = {
        name: name,
        block_id: id
      };

      expect($scope.isNameInvalid(disk)).toBe(true);
    });

    it("returns false if name is the same as self", function() {
      makeController();
      var id = makeInteger(100, 200);
      var name = makeName("name");
      var thisDisk = {
        id: id,
        type: "physical",
        name: name
      };

      $scope.node.disks = [thisDisk];
      var disk = {
        name: name,
        type: "physical",
        block_id: id
      };

      expect($scope.isNameInvalid(disk)).toBe(false);
    });
  });

  describe("nameHasChanged", function() {
    it("logical volume resets name to include parents name", function() {
      makeController();
      var disk = {
        name: "",
        type: "virtual",
        parent_type: "lvm-vg",
        original: {
          name: "vg0-lvname"
        }
      };

      $scope.nameHasChanged(disk);
      expect(disk.name).toBe("vg0-");
    });
  });

  describe("availableCancel", function() {
    it("calls updateAvailableSelection with force true", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");

      $scope.availableCancel(available[0].$selected);

      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("usesMountPoint", function() {
    it("returns false if filesystem is undefined", function() {
      makeController();

      expect($scope.usesMountPoint(undefined)).toBe(false);
    });

    it("returns false if filesystem is null", function() {
      makeController();

      expect($scope.usesMountPoint(null)).toBe(false);
    });

    it("returns false if filesystem is not a string", function() {
      makeController();

      expect($scope.usesMountPoint(1234)).toBe(false);
    });

    it("returns false if filesystem is 'swap'", function() {
      makeController();

      expect($scope.usesMountPoint("swap")).toBe(false);
    });

    it("returns true if filesystem is not 'swap'", function() {
      makeController();

      expect($scope.usesMountPoint("any-string")).toBe(true);
    });
  });

  describe("isMountPointInvalid", function() {
    it("returns false if mount_point is undefined", function() {
      makeController();

      expect($scope.isMountPointInvalid()).toBe(false);
    });

    it("returns false if mount_point is empty", function() {
      makeController();

      expect($scope.isMountPointInvalid("")).toBe(false);
    });

    it("returns false if mount_point is 'none'", function() {
      makeController();

      expect($scope.isMountPointInvalid("none")).toBe(false);
    });

    it("returns true if mount_point doesn't start with '/'", function() {
      makeController();

      expect($scope.isMountPointInvalid("a")).toBe(true);
    });

    it("returns false if mount_point start with '/'", function() {
      makeController();

      expect($scope.isMountPointInvalid("/")).toBe(false);
    });
  });

  describe("canDelete", function() {
    it("returns true if volume group not used", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        fstype: null,
        has_partitions: false,
        original: {
          used_size: 0
        }
      };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(true);
    });

    it("returns false if not super user", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        fstype: null,
        has_partitions: false,
        original: {
          used_size: 0
        }
      };
      $scope.canEdit = function() {
        return false;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(false);
    });

    it("returns false if isAllStorageDisabled", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        fstype: null,
        has_partitions: false,
        original: {
          used_size: 0
        }
      };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);

      expect($scope.canDelete(disk)).toBe(false);
    });

    it("returns false if volume group used", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        fstype: null,
        has_partitions: false,
        original: {
          used_size: makeInteger(100, 10000)
        }
      };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(false);
    });

    it("returns true if fstype is null", function() {
      makeController();
      var disk = { fstype: null, has_partitions: false };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(true);
    });

    it("returns true if fstype is empty", function() {
      makeController();
      var disk = { fstype: "", has_partitions: false };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(true);
    });

    it("returns true if fstype is not empty", function() {
      makeController();
      var disk = { fstype: "ext4" };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(true);
    });

    it("returns false if has_partitions is true", function() {
      makeController();
      var disk = { fstype: "", has_partitions: true };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDelete(disk)).toBe(false);
    });
  });

  describe("canDeleteFilesystem", function() {
    it("returns true if special", function() {
      makeController();
      var filesystem = {
        original_type: "special"
      };
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canDeleteFilesystem(filesystem)).toBe(true);
    });

    it("returns canEdit otherwise", function() {
      makeController();
      var filesystem = {
        original_type: "other"
      };
      $scope.canEdit = function() {
        return false;
      };

      expect($scope.canDeleteFilesystem(filesystem)).toBe(false);
    });
  });

  describe("availableDelete", function() {
    it("sets availableMode to DELETE", function() {
      makeController();
      $scope.availableMode = "other";

      $scope.availableDelete();

      expect($scope.availableMode).toBe("delete");
    });
  });

  describe("availableQuickDelete", function() {
    it("selects disks and deselects others", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      $scope.available = available;
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableDelete");

      $scope.availableQuickDelete(available[0]);

      expect(available[0].$selected).toBe(true);
      expect(available[1].$selected).toBe(false);
    });

    it("calls updateAvailableSelection with force true", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableDelete");

      $scope.availableQuickDelete(available[0]);

      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls availableDelete", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableDelete");

      $scope.availableQuickDelete(available[0]);

      expect($scope.availableDelete).toHaveBeenCalledWith();
    });
  });

  describe("getRemoveTypeText", function() {
    it("returns 'physical disk' for physical on filesystem", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "filesystem",
          original: {
            type: "physical"
          }
        })
      ).toBe("physical disk");
    });

    it("returns 'physical disk' for physical", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "physical"
        })
      ).toBe("physical disk");
    });

    it("returns 'partition' for partition", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "partition"
        })
      ).toBe("partition");
    });

    it("returns 'volume group' for lvm-vg", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "lvm-vg"
        })
      ).toBe("volume group");
    });

    it("returns 'logical volume' for virtual on lvm-vg", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "virtual",
          parent_type: "lvm-vg"
        })
      ).toBe("logical volume");
    });

    it("returns 'RAID %d' for virtual on raid", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "virtual",
          parent_type: "raid-1"
        })
      ).toBe("RAID 1 disk");
    });

    it("returns parent_type + 'disk' for other virtual", function() {
      makeController();
      expect(
        $scope.getRemoveTypeText({
          type: "virtual",
          parent_type: "raid0"
        })
      ).toBe("raid0 disk");
    });
  });

  describe("availableConfirmDelete", function() {
    it("calls MachinesManager.deleteVolumeGroup for lvm-vg", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100)
      };
      $scope.available = [disk];
      spyOn(MachinesManager, "deleteVolumeGroup");
      spyOn($scope, "updateAvailableSelection");

      $scope.availableConfirmDelete(disk);
      expect(MachinesManager.deleteVolumeGroup).toHaveBeenCalledWith(
        node,
        disk.block_id
      );
      expect($scope.available).toEqual([]);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls MachinesManager.deletePartition for partition", function() {
      makeController();
      var disk = {
        type: "partition",
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100)
      };
      $scope.available = [disk];
      spyOn(MachinesManager, "deletePartition");
      spyOn($scope, "updateAvailableSelection");

      $scope.availableConfirmDelete(disk);
      expect(MachinesManager.deletePartition).toHaveBeenCalledWith(
        node,
        disk.partition_id
      );
      expect($scope.available).toEqual([]);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls MachinesManager.deleteDisk for disk", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100)
      };
      $scope.available = [disk];
      spyOn(MachinesManager, "deleteDisk");
      spyOn($scope, "updateAvailableSelection");

      $scope.availableConfirmDelete(disk);
      expect(MachinesManager.deleteDisk).toHaveBeenCalledWith(
        node,
        disk.block_id
      );
      expect($scope.available).toEqual([]);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("availablePartition", function() {
    it("sets availableMode to 'partition'", function() {
      makeController();
      var disk = {
        available_size_human: "10 GB"
      };
      $scope.availableMode = "other";
      $scope.availablePartition(disk);
      expect($scope.availableMode).toBe("partition");
    });

    it("sets $options to values from available_size_human", function() {
      makeController();
      var disk = {
        available_size_human: "10 GB"
      };
      $scope.availablePartition(disk);
      expect(disk.$options).toEqual({
        size: "10",
        sizeUnits: "GB",
        fstype: null,
        mountPoint: "",
        mountOptions: ""
      });
    });
  });

  describe("availableQuickPartition", function() {
    it("selects disks and deselects others", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      $scope.available = available;
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availablePartition");

      $scope.availableQuickPartition(available[0]);

      expect(available[0].$selected).toBe(true);
      expect(available[1].$selected).toBe(false);
    });

    it("calls updateAvailableSelection with force true", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availablePartition");

      $scope.availableQuickPartition(available[0]);

      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls availablePartition", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availablePartition");

      $scope.availableQuickPartition(available[0]);

      expect($scope.availablePartition).toHaveBeenCalledWith(available[0]);
    });
  });

  describe("getAddPartitionName", function() {
    it("returns disk.name with -part#", function() {
      makeController();
      var name = makeName("sda");
      var disk = {
        name: name,
        original: {
          partition_table_type: "gpt",
          partitions: [{}, {}]
        }
      };

      expect($scope.getAddPartitionName(disk)).toBe(name + "-part3");
    });

    it("returns disk.name with -part2 for ppc64el", function() {
      node.architecture = "ppc64el/generic";
      makeController();
      var name = makeName("sda");
      var disk = {
        name: name,
        original: {
          is_boot: true,
          partition_table_type: "gpt"
        }
      };

      expect($scope.getAddPartitionName(disk)).toBe(name + "-part2");
    });

    it("returns disk.name with -part4 for ppc64el", function() {
      node.architecture = "ppc64el/generic";
      makeController();
      var name = makeName("sda");
      var disk = {
        name: name,
        original: {
          is_boot: true,
          partition_table_type: "gpt",
          partitions: [{}, {}]
        }
      };

      expect($scope.getAddPartitionName(disk)).toBe(name + "-part4");
    });

    it("returns disk.name with -part3 for MBR", function() {
      makeController();
      var name = makeName("sda");
      var disk = {
        name: name,
        original: {
          partition_table_type: "mbr",
          partitions: [{}, {}]
        }
      };

      expect($scope.getAddPartitionName(disk)).toBe(name + "-part3");
    });

    it("returns disk.name with -part5 for MBR", function() {
      makeController();
      var name = makeName("sda");
      var disk = {
        name: name,
        original: {
          partition_table_type: "mbr",
          partitions: [{}, {}, {}]
        }
      };

      expect($scope.getAddPartitionName(disk)).toBe(name + "-part5");
    });
  });

  describe("isAddPartitionSizeInvalid", function() {
    it("returns true if blank", function() {
      makeController();
      var size = "";
      var disk = {
        $options: {
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(true);
    });

    it("returns true if not numbers", function() {
      makeController();
      var size = makeName("invalid");
      var disk = {
        $options: {
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(true);
    });

    it("returns true if smaller than MIN_PARTITION_SIZE", function() {
      makeController();
      var size = "1";
      var disk = {
        $options: {
          sizeUnits: "MB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(true);
    });

    it(`returns true if larger than available_size
        more than tolerance`, function() {
      makeController();
      var size = "4";
      var disk = {
        original: {
          available_size: 2 * 1000 * 1000 * 1000
        },
        $options: {
          size: "4",
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(true);
    });

    it("returns false if larger than available_size in tolerance", function() {
      makeController();
      var size = "2.62";
      var disk = {
        original: {
          available_size: 2.6 * 1000 * 1000 * 1000
        },
        $options: {
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(false);
    });

    it("returns false if less than available_size", function() {
      makeController();
      var size = "1.6";
      var disk = {
        original: {
          available_size: 2.6 * 1000 * 1000 * 1000
        },
        $options: {
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      expect($scope.isAddPartitionSizeInvalid(disk)).toBe(false);
    });
  });

  describe("availableConfirmPartition", function() {
    it("does nothing if invalid", function() {
      makeController();
      var size = "";
      var disk = {
        $options: {
          sizeUnits: "GB"
        }
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.returnValue(size);
      $scope.$digest();

      spyOn(MachinesManager, "createPartition");

      $scope.availableConfirmPartition(disk);

      expect(MachinesManager.createPartition).not.toHaveBeenCalled();
    });

    it("calls createPartition with bytes", function() {
      makeController();
      var disk = {
        block_id: makeInteger(0, 100),
        original: {
          partition_table_type: "mbr",
          available_size: 4 * 1000 * 1000 * 1000,
          available_size_human: "4.0 GB",
          block_size: 512
        },
        $options: {
          sizeUnits: "GB"
        }
      };
      var params = {
        size: "2",
        mount_point: makeName("/path"),
        mount_options: makeName("options")
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.callFake(function(
        param
      ) {
        return params[param];
      });
      $scope.$digest();

      $scope.availableConfirmPartition(disk);

      expect($scope.newPartition.system_id).toEqual(node.system_id);
      expect($scope.newPartition.block_id).toEqual(disk.block_id);
      expect($scope.newPartition.partition_size).toEqual(
        2 * 1000 * 1000 * 1000
      );
    });

    it(
      "calls createPartition with fstype, " + "mountPoint, and mountOptions",
      function() {
        makeController();
        var disk = {
          block_id: makeInteger(0, 100),
          original: {
            partition_table_type: "mbr",
            available_size: 4 * 1000 * 1000 * 1000,
            available_size_human: "4.0 GB",
            block_size: 512
          },
          $options: {
            sizeUnits: "GB",
            fstype: "ext4"
          }
        };
        var params = {
          size: "2",
          mount_point: makeName("/path"),
          mount_options: makeName("options")
        };
        $scope.newPartition.$maasForm = { getValue: function() {} };
        spyOn($scope.newPartition.$maasForm, "getValue").and.callFake(function(
          param
        ) {
          return params[param];
        });
        $scope.$digest();

        $scope.availableConfirmPartition(disk);

        expect($scope.newPartition.params).toEqual({
          fstype: "ext4",
          mount_point: params["mount_point"],
          mount_options: params["mount_options"]
        });
      }
    );

    it("calls createPartition with available_size bytes", function() {
      makeController();
      var available_size = 2.6 * 1000 * 1000 * 1000;
      var disk = {
        block_id: makeInteger(0, 100),
        original: {
          partition_table_type: "mbr",
          available_size: available_size,
          available_size_human: "2.6 GB",
          block_size: 512
        },
        $options: {
          sizeUnits: "GB"
        }
      };
      var params = {
        size: "2.62",
        mount_point: makeName("/path"),
        mount_options: makeName("options")
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.callFake(function(
        param
      ) {
        return params[param];
      });
      $scope.$digest();

      $scope.availableConfirmPartition(disk);

      // Align to 4MiB.
      var align_size = 4 * 1024 * 1024;
      var expected = align_size * Math.floor(available_size / align_size);

      expect($scope.newPartition.partition_size).toEqual(expected);
    });

    // regression test for https://bugs.launchpad.net/maas/+bug/1509535
    it(
      "calls createPartition with available_size bytes" +
        " even when human size gets rounded down",
      function() {
        makeController();
        var available_size = 2.035 * 1000 * 1000 * 1000;
        var disk = {
          block_id: makeInteger(0, 100),
          original: {
            partition_table_type: "mbr",
            available_size: available_size,
            available_size_human: "2.0 GB",
            block_size: 512
          },
          $options: {
            sizeUnits: "GB"
          }
        };
        var params = {
          size: "2.0",
          mount_point: makeName("/path"),
          mount_options: makeName("options")
        };
        $scope.newPartition.$maasForm = { getValue: function() {} };
        spyOn($scope.newPartition.$maasForm, "getValue").and.callFake(function(
          param
        ) {
          return params[param];
        });
        $scope.$digest();

        $scope.availableConfirmPartition(disk);

        // Align to 4MiB.
        var align_size = 4 * 1024 * 1024;
        var expected = align_size * Math.floor(available_size / align_size);

        expect($scope.newPartition.partition_size).toEqual(expected);
      }
    );

    it(`calls createPartition with bytes
        minus partition table extra`, function() {
      makeController();
      var available_size = 2.6 * 1000 * 1000 * 1000;
      var disk = {
        block_id: makeInteger(0, 100),
        original: {
          partition_table_type: "",
          available_size: available_size,
          available_size_human: "2.6 GB",
          block_size: 512
        },
        $options: {
          sizeUnits: "GB"
        }
      };
      var params = {
        size: "2.62",
        mount_point: makeName("/path"),
        mount_options: makeName("options")
      };
      $scope.newPartition.$maasForm = { getValue: function() {} };
      spyOn($scope.newPartition.$maasForm, "getValue").and.callFake(function(
        param
      ) {
        return params[param];
      });
      $scope.$digest();

      $scope.availableConfirmPartition(disk);

      // Remove partition extra space and align to 4MiB.
      var align_size = 4 * 1024 * 1024;
      var expected =
        align_size *
        Math.floor((available_size - 5 * 1024 * 1024) / align_size);

      expect($scope.newPartition.partition_size).toEqual(expected);
    });
  });

  describe("getSelectedCacheSets", function() {
    it("returns selected cachesets", function() {
      makeController();
      var cachesets = [
        { $selected: true },
        { $selected: true },
        { $selected: false },
        { $selected: false }
      ];
      $scope.cachesets = cachesets;
      expect($scope.getSelectedCacheSets()).toEqual([
        cachesets[0],
        cachesets[1]
      ]);
    });
  });

  describe("updateCacheSetsSelection", function() {
    it("sets cachesetsMode to NONE when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([]);
      $scope.cachesetsMode = "other";

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsMode).toBeNull();
    });

    it("doesn't sets cachesetsMode to SINGLE when not force", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}]);
      $scope.cachesetsMode = "other";

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsMode).toBe("other");
    });

    it("sets cachesetsMode to SINGLE when force", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}]);
      $scope.cachesetsMode = "other";

      $scope.updateCacheSetsSelection(true);

      expect($scope.cachesetsMode).toBe("single");
    });

    it("doesn't sets cachesetsMode to MUTLI when not force", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}, {}]);
      $scope.cachesetsMode = "other";

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsMode).toBe("other");
    });

    it("sets cachesetsMode to MULTI when force", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}, {}]);
      $scope.cachesetsMode = "other";

      $scope.updateCacheSetsSelection(true);

      expect($scope.cachesetsMode).toBe("multi");
    });

    it("sets cachesetsAllSelected to false when none selected", function() {
      makeController();
      spyOn($scope, "getSelectedCacheSets").and.returnValue([]);
      $scope.cachesetsAllSelected = true;

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsAllSelected).toBe(false);
    });

    it("sets cachesetsAllSelected to false when not all selected", function() {
      makeController();
      $scope.cachesets = [{}, {}];
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}]);
      $scope.cachesetsAllSelected = true;

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsAllSelected).toBe(false);
    });

    it("sets cachesetsAllSelected to true when all selected", function() {
      makeController();
      $scope.cachesets = [{}, {}];
      spyOn($scope, "getSelectedCacheSets").and.returnValue([{}, {}]);
      $scope.cachesetsAllSelected = false;

      $scope.updateCacheSetsSelection();

      expect($scope.cachesetsAllSelected).toBe(true);
    });
  });

  describe("toggleCacheSetSelect", function() {
    it("inverts $selected", function() {
      makeController();
      var cacheset = { $selected: true };
      spyOn($scope, "updateCacheSetsSelection");

      $scope.toggleCacheSetSelect(cacheset);

      expect(cacheset.$selected).toBe(false);
      $scope.toggleCacheSetSelect(cacheset);
      expect(cacheset.$selected).toBe(true);
      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("toggleCacheSetAllSelect", function() {
    it("sets all to true if not all selected", function() {
      makeController();
      var cachesets = [{ $selected: true }, { $selected: false }];
      $scope.cachesets = cachesets;
      $scope.cachesetsAllSelected = false;
      spyOn($scope, "updateCacheSetsSelection");

      $scope.toggleCacheSetAllSelect();

      expect(cachesets[0].$selected).toBe(true);
      expect(cachesets[1].$selected).toBe(true);
      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith(true);
    });

    it("sets all to false if all selected", function() {
      makeController();
      var cachesets = [{ $selected: true }, { $selected: true }];
      $scope.cachesets = cachesets;
      $scope.cachesetsAllSelected = true;
      spyOn($scope, "updateCacheSetsSelection");

      $scope.toggleCacheSetAllSelect();

      expect(cachesets[0].$selected).toBe(false);
      expect(cachesets[1].$selected).toBe(false);
      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("isCacheSetsDisabled", function() {
    it("returns false for NONE", function() {
      makeController();
      $scope.cachesetsMode = null;
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isCacheSetsDisabled()).toBe(false);
    });

    it("returns false for SINGLE", function() {
      makeController();
      $scope.cachesetsMode = "single";
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isCacheSetsDisabled()).toBe(false);
    });

    it("returns false for MULTI", function() {
      makeController();
      $scope.cachesetsMode = "multi";
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isCacheSetsDisabled()).toBe(false);
    });

    it("returns true for when not super user", function() {
      makeController();
      $scope.cachesetsMode = "delete";
      $scope.canEdit = function() {
        return false;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isCacheSetsDisabled()).toBe(true);
    });

    it("returns true for when isAllStorageDisabled", function() {
      makeController();
      $scope.cachesetsMode = "delete";
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);

      expect($scope.isCacheSetsDisabled()).toBe(true);
    });

    it("returns true for DELETE", function() {
      makeController();
      $scope.cachesetsMode = "delete";
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.isCacheSetsDisabled()).toBe(true);
    });
  });

  describe("cacheSetCancel", function() {
    it("calls updateCacheSetsSelection with force true", function() {
      makeController();
      spyOn($scope, "updateCacheSetsSelection");

      $scope.cacheSetCancel();

      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("canDeleteCacheSet", function() {
    it("returns true when not being used", function() {
      makeController();
      var cacheset = { used_by: "" };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDeleteCacheSet(cacheset)).toBe(true);
    });

    it("returns false when being used", function() {
      makeController();
      var cacheset = { used_by: "bcache0" };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDeleteCacheSet(cacheset)).toBe(false);
    });

    it("returns false when not super user", function() {
      makeController();
      var cacheset = { used_by: "" };
      $scope.canEdit = function() {
        return false;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);

      expect($scope.canDeleteCacheSet(cacheset)).toBe(false);
    });

    it("returns false when isAllStorageDisabled", function() {
      makeController();
      var cacheset = { used_by: "" };
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);

      expect($scope.canDeleteCacheSet(cacheset)).toBe(false);
    });
  });

  describe("cacheSetDelete", function() {
    it("sets cachesetsMode to DELETE", function() {
      makeController();
      $scope.cachesetsMode = "other";

      $scope.cacheSetDelete();

      expect($scope.cachesetsMode).toBe("delete");
    });
  });

  describe("quickCacheSetDelete", function() {
    it("selects cacheset and calls cacheSetDelete", function() {
      makeController();
      var cachesets = [{ $selected: true }, { $selected: false }];
      $scope.cachesets = cachesets;
      spyOn($scope, "updateCacheSetsSelection");
      spyOn($scope, "cacheSetDelete");

      $scope.quickCacheSetDelete(cachesets[1]);

      expect(cachesets[0].$selected).toBe(false);
      expect(cachesets[1].$selected).toBe(true);
      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith(true);
      expect($scope.cacheSetDelete).toHaveBeenCalled();
    });
  });

  describe("cacheSetConfirmDelete", function() {
    it(`calls MachinesManager.deleteCacheSet
        and removes from list`, function() {
      makeController();
      var cacheset = {
        cache_set_id: makeInteger(0, 100)
      };
      $scope.cachesets = [cacheset];
      spyOn(MachinesManager, "deleteCacheSet");
      spyOn($scope, "updateCacheSetsSelection");

      $scope.cacheSetConfirmDelete(cacheset);

      expect(MachinesManager.deleteCacheSet).toHaveBeenCalledWith(
        node,
        cacheset.cache_set_id
      );
      expect($scope.cachesets).toEqual([]);
      expect($scope.updateCacheSetsSelection).toHaveBeenCalledWith();
    });
  });

  describe("canCreateCacheSet", function() {
    it("returns false if isAvailableDisabled returns true", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateCacheSet()).toBe(false);
    });

    it("returns false if two selected", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [{ $selected: true }, { $selected: true }];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateCacheSet()).toBe(false);
    });

    it("returns false if selected has fstype", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: "ext4",
          $selected: true
        }
      ];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateCacheSet()).toBe(false);
    });

    it("returns false if selected is volume group", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          type: "lvm-vg",
          fstype: null,
          $selected: true
        }
      ];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateCacheSet()).toBe(false);
    });

    it("returns false if not super user", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true
        }
      ];
      $scope.canEdit = function() {
        return false;
      };

      expect($scope.canCreateCacheSet()).toBe(false);
    });

    it("returns true if selected has no fstype", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true
        }
      ];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateCacheSet()).toBe(true);
    });
  });

  describe("createCacheSet", function() {
    it("does nothing if canCreateCacheSet returns false", function() {
      makeController();
      var disk = {
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        $selected: true
      };
      $scope.available = [disk];
      spyOn($scope, "canCreateCacheSet").and.returnValue(false);
      spyOn(MachinesManager, "createCacheSet");

      $scope.createCacheSet();
      expect(MachinesManager.createCacheSet).not.toHaveBeenCalled();
    });

    it(`calls MachinesManager.createCacheSet and
        removes from available`, function() {
      makeController();
      var disk = {
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        $selected: true
      };
      $scope.available = [disk];
      spyOn($scope, "canCreateCacheSet").and.returnValue(true);
      spyOn(MachinesManager, "createCacheSet");

      $scope.createCacheSet();
      expect(MachinesManager.createCacheSet).toHaveBeenCalledWith(
        node,
        disk.block_id,
        disk.partition_id
      );
      expect($scope.available).toEqual([]);
    });
  });

  describe("getCannotCreateBcacheMsg", function() {
    it("returns msg if no cachesets", function() {
      makeController();
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [];
      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Create at least one cache set to create bcache"
      );
    });

    it("returns msg if two selected", function() {
      makeController();
      $scope.cachesets = [{}];
      $scope.available = [{ $selected: true }, { $selected: true }];
      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Select only one available device to create bcache"
      );
    });

    it("returns msg if selected has fstype", function() {
      makeController();
      $scope.available = [
        {
          fstype: "ext4",
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];

      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Device is formatted; unformat the device to create bcache"
      );
    });

    it("returns msg if selected is volume group", function() {
      makeController();
      $scope.available = [
        {
          type: "lvm-vg",
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Cannot use a logical volume as a backing device for bcache."
      );
    });

    it("returns msg if selected has partitions", function() {
      makeController();
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: true
        }
      ];
      $scope.cachesets = [{}];
      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Device has already been partitioned; create a " +
          "new partition to use as the bcache backing " +
          "device"
      );
    });

    it("returns msg if selected is bcache", function() {
      makeController();
      $scope.available = [
        {
          $selected: true,
          parent_type: "bcache"
        }
      ];
      $scope.cachesets = [{}];
      expect($scope.getCannotCreateBcacheMsg()).toBe(
        "Device is already bcache"
      );
    });

    it("returns null if selected is valid", function() {
      makeController();
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      expect($scope.getCannotCreateBcacheMsg()).toBeNull();
    });
  });

  describe("canEdit", function() {
    it("returns false when $parent.canEdit is false", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      $scope.$parent.canEdit = function() {
        return false;
      };

      expect($scope.canEdit()).toBe(false);
    });

    it("returns false when isAllStorageDisabled is false", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(true);
      $scope.$parent.canEdit = function() {
        return true;
      };

      expect($scope.canEdit()).toBe(false);
    });

    it("returns true when partition", function() {
      makeController();
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      var disk = {
        type: "partition"
      };

      expect($scope.canEdit(disk)).toBe(true);
    });
  });

  describe("availableEdit", function() {
    it("calls availableEdit for volumn group", function() {
      makeController();
      var disk = {
        type: "lvm-vg"
      };
      $scope.availableEdit(disk);
      expect(disk.$options).toEqual({
        editingTags: false,
        editingFilesystem: false
      });
    });

    it("calls availableEdit for partition", function() {
      makeController();
      var disk = {
        type: "partition"
      };
      $scope.availableEdit(disk);
      expect(disk.$options).toEqual({
        editingTags: false,
        editingFilesystem: true,
        fstype: disk.fstype
      });
    });

    it("calls availableEdit for disk with partitions", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: true
      };
      $scope.availableEdit(disk);
      expect(disk.$options).toEqual({
        editingFilesystem: false,
        editingTags: true,
        tags: undefined,
        fstype: undefined
      });
    });

    it("calls availableEdit for disk and is boot disk", function() {
      makeController();
      var disk = {
        type: "physical",
        has_partitions: false,
        original: {
          is_boot: true
        }
      };
      $scope.availableEdit(disk);
      expect(disk.$options).toEqual({
        editingFilesystem: false,
        editingTags: true,
        tags: undefined,
        fstype: undefined
      });
    });
  });

  describe("availableQuickEdit", function() {
    it("selects disks and deselects others", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      $scope.available = available;
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableEdit");

      $scope.availableQuickEdit(available[0]);

      expect(available[0].$selected).toBe(true);
      expect(available[1].$selected).toBe(false);
    });

    it("calls updateAvailableSelection with force true", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableEdit");

      $scope.availableQuickEdit(available[0]);

      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls availableEdit", function() {
      makeController();
      var available = [{ $selected: false }, { $selected: true }];
      spyOn($scope, "updateAvailableSelection");
      spyOn($scope, "availableEdit");

      $scope.availableQuickEdit(available[0]);

      expect($scope.availableEdit).toHaveBeenCalledWith(available[0]);
    });
  });

  describe("availableConfirmEdit", function() {
    it("does nothing if invalid", function() {
      makeController();
      var disk = {
        $options: {
          mountPoint: "!#$%"
        }
      };
      spyOn(MachinesManager, "updateDisk");

      $scope.availableConfirmEdit(disk);
      expect(MachinesManager.updateDisk).not.toHaveBeenCalled();
    });

    it("resets name to original if empty", function() {
      makeController();
      var name = makeName("name");
      var disk = {
        name: "",
        $options: {
          mountPoint: ""
        },
        original: {
          name: name
        }
      };
      spyOn(MachinesManager, "updateDisk");

      $scope.availableConfirmEdit(disk);
      expect(disk.name).toBe(name);
      expect(MachinesManager.updateDisk).toHaveBeenCalled();
    });

    it("calls updateDisk with new name for logical volume", function() {
      makeController();
      var name = "vg0-lvnew";
      var disk = {
        name: name,
        type: "virtual",
        parent_type: "lvm-vg",
        block_id: makeInteger(0, 100),
        partition_id: makeInteger(0, 100),
        $options: {
          fstype: "",
          mountPoint: "",
          mountOptions: ""
        },
        original: {
          name: "vg0-lvold"
        }
      };
      spyOn(MachinesManager, "updateDisk");

      $scope.availableConfirmEdit(disk);
      expect(disk.name).toBe(name);
      expect(MachinesManager.updateDisk).toHaveBeenCalled();
    });

    it("calls updateFilesystem for partition", function() {
      makeController();
      var name = makeName("name");
      var disk = {
        name: "",
        type: "partition",
        $options: {
          mountPoint: ""
        },
        original: {
          name: name
        }
      };
      spyOn(MachinesManager, "updateFilesystem");

      $scope.availableConfirmEdit(disk);
      expect(disk.name).toBe(name);
      expect(MachinesManager.updateFilesystem).toHaveBeenCalled();
    });
  });

  describe("canCreateBcache", function() {
    it("returns false when isAvailableDisabled is true", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if two selected", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [{ $selected: true }, { $selected: true }];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if selected has fstype", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: "ext4",
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if selected is volume group", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          type: "lvm-vg",
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if selected has partitions", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: true
        }
      ];
      $scope.cachesets = [{}];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it(`returns false if selected has no fstype
        but not cachesets`, function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if not super user ", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      $scope.canEdit = function() {
        return false;
      };

      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns false if selected is bcache", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          $selected: true,
          parent_type: "bcache"
        }
      ];
      expect($scope.canCreateBcache()).toBe(false);
    });

    it("returns true if selected has no fstype but has cachesets ", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      $scope.available = [
        {
          fstype: null,
          $selected: true,
          has_partitions: false
        }
      ];
      $scope.cachesets = [{}];
      $scope.canEdit = function() {
        return true;
      };

      expect($scope.canCreateBcache()).toBe(true);
    });
  });

  describe("createBcache", function() {
    it("does nothing if canCreateBcache returns false", function() {
      makeController();
      $scope.availableMode = "other";
      spyOn($scope, "canCreateBcache").and.returnValue(false);

      $scope.createBcache();
      expect($scope.availableMode).toBe("other");
    });

    it("sets availableMode and availableNew", function() {
      makeController();
      $scope.availableMode = "other";
      spyOn($scope, "canCreateBcache").and.returnValue(true);

      // Add bcache name to create a name after that index.
      var otherBcache = {
        name: "bcache4"
      };
      node.disks = [otherBcache];

      // Will be set as the device.
      var disk = {
        $selected: true
      };
      $scope.available = [disk];

      // Will be set as the cacheset.
      var cacheset = {};
      $scope.cachesets = [cacheset];

      $scope.createBcache();
      expect($scope.availableMode).toBe("bcache");
      expect($scope.availableNew).toEqual({
        name: "bcache5",
        device: disk,
        cacheset: cacheset,
        cacheMode: "writeback",
        fstype: null,
        mountPoint: "",
        mountOptions: "",
        tags: []
      });
      expect($scope.availableNew.device).toBe(disk);
      expect($scope.availableNew.cacheset).toBe(cacheset);
    });
  });

  describe("fstypeChanged", function() {
    it("leaves mountPoint when fstype is not null", function() {
      makeController();
      var mountPoint = makeName("srv");
      var mountOptions = makeName("options");
      var options = {
        fstype: "ext4",
        mountPoint: mountPoint,
        mountOptions: mountOptions
      };

      $scope.fstypeChanged(options);
      expect(options.mountPoint).toBe(mountPoint);
      expect(options.mountOptions).toBe(mountOptions);
    });

    it("clears mountPoint when fstype null", function() {
      makeController();
      var options = {
        fstype: null,
        mountPoint: makeName("srv"),
        mountOptions: makeName("options")
      };

      $scope.fstypeChanged(options);
      expect(options.mountPoint).toBe("");
      expect(options.mountOptions).toBe("");
    });

    it(
      "sets mountPoint to 'none' for a partition that " +
        "cannot be mounted at a directory",
      function() {
        makeController();
        var mountPoint = makeName("srv");
        var mountOptions = makeName("options");
        var options = {
          fstype: "swap",
          mountPoint: mountPoint,
          mountOptions: mountOptions
        };

        $scope.fstypeChanged(options);
        expect(options.mountPoint).toBe("none");
        // Mount options are unchanged.
        expect(options.mountOptions).toBe(mountOptions);
      }
    );

    it(
      "clears mountPoint from 'none' for a partition that " +
        "can be mounted at a directory",
      function() {
        makeController();
        var mountOptions = makeName("options");
        var options = {
          fstype: "ext4",
          mountPoint: "none",
          mountOptions: mountOptions
        };

        $scope.fstypeChanged(options);
        expect(options.mountPoint).toBe("");
        // Mount options are unchanged.
        expect(options.mountOptions).toBe(mountOptions);
      }
    );
  });

  describe("isNewDiskNameInvalid", function() {
    it("returns true if blank name", function() {
      makeController();
      $scope.node.disks = [];

      expect($scope.isNewDiskNameInvalid("")).toBe(true);
    });

    it("returns true if name used by disk", function() {
      makeController();
      var name = makeName("disk");
      $scope.node.disks = [
        {
          name: name
        }
      ];

      expect($scope.isNewDiskNameInvalid(name)).toBe(true);
    });

    it("returns true if name used by partition", function() {
      makeController();
      var name = makeName("disk");
      $scope.node.disks = [
        {
          name: makeName("other"),
          partitions: [
            {
              name: name
            }
          ]
        }
      ];

      expect($scope.isNewDiskNameInvalid(name)).toBe(true);
    });

    it("returns false if the name is not already used", function() {
      makeController();
      var name = makeName("disk");
      $scope.node.disks = [
        {
          name: makeName("other"),
          partitions: [
            {
              name: makeName("part")
            }
          ]
        }
      ];

      expect($scope.isNewDiskNameInvalid(name)).toBe(false);
    });
  });

  describe("createBcacheCanSave", function() {
    it("returns false if isNewDiskNameInvalid returns true", function() {
      makeController();
      $scope.availableNew.mountPoint = "/";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(true);

      expect($scope.createBcacheCanSave()).toBe(false);
    });

    it("returns false if isMountPointInvalid returns true", function() {
      makeController();
      $scope.availableNew.mountPoint = "not/absolute";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(false);

      expect($scope.createBcacheCanSave()).toBe(false);
    });

    it("returns true if both return false", function() {
      makeController();
      $scope.availableNew.mountPoint = "/";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(false);

      expect($scope.createBcacheCanSave()).toBe(true);
    });
  });

  describe("availableConfirmCreateBcache", function() {
    it("does nothing if createBcacheCanSave returns false", function() {
      makeController();
      spyOn($scope, "createBcacheCanSave").and.returnValue(false);
      var availableNew = {
        name: makeName("bcache"),
        cacheset: {
          cache_set_id: makeInteger(0, 100)
        },
        cacheMode: "writearound",
        device: {
          type: "partition",
          partition_id: makeInteger(0, 100)
        },
        fstype: null,
        mountPoint: "",
        mountOptions: ""
      };
      $scope.availableNew = availableNew;
      spyOn(MachinesManager, "createBcache");

      $scope.availableConfirmCreateBcache();
      expect(MachinesManager.createBcache).not.toHaveBeenCalled();
    });

    it("calls MachinesManager.createBcache for partition", function() {
      makeController();
      spyOn($scope, "createBcacheCanSave").and.returnValue(true);
      var device = {
        type: "partition",
        partition_id: makeInteger(0, 100),
        $selected: true
      };
      var availableNew = {
        name: makeName("bcache"),
        cacheset: {
          cache_set_id: makeInteger(0, 100)
        },
        cacheMode: "writearound",
        device: device,
        fstype: "ext4",
        mountPoint: makeName("/path"),
        mountOptions: makeName("options")
      };
      $scope.available = [device];
      $scope.availableNew = availableNew;
      spyOn(MachinesManager, "createBcache");
      spyOn($scope, "updateAvailableSelection");

      $scope.availableConfirmCreateBcache();
      expect(MachinesManager.createBcache).toHaveBeenCalledWith(node, {
        name: availableNew.name,
        cache_set: availableNew.cacheset.cache_set_id,
        cache_mode: "writearound",
        partition_id: device.partition_id,
        fstype: "ext4",
        mount_point: availableNew.mountPoint,
        mount_options: availableNew.mountOptions
      });
      expect($scope.available).toEqual([]);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });

    it("calls MachinesManager.createBcache for block device", function() {
      makeController();
      spyOn($scope, "createBcacheCanSave").and.returnValue(true);
      var device = {
        type: "physical",
        block_id: makeInteger(0, 100),
        $selected: true
      };
      var availableNew = {
        name: makeName("bcache"),
        cacheset: {
          cache_set_id: makeInteger(0, 100)
        },
        cacheMode: "writearound",
        device: device,
        fstype: null,
        mountPoint: "/",
        mountOptions: makeName("options")
      };
      $scope.available = [device];
      $scope.availableNew = availableNew;
      spyOn(MachinesManager, "createBcache");
      spyOn($scope, "updateAvailableSelection");

      $scope.availableConfirmCreateBcache();
      expect(MachinesManager.createBcache).toHaveBeenCalledWith(node, {
        name: availableNew.name,
        cache_set: availableNew.cacheset.cache_set_id,
        cache_mode: "writearound",
        block_id: device.block_id
      });
      expect($scope.available).toEqual([]);
      expect($scope.updateAvailableSelection).toHaveBeenCalledWith(true);
    });
  });

  describe("canCreateRAID", function() {
    it("returns false isAvailableDisabled returns true", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateRAID()).toBe(false);
    });

    it("returns false if less than 2 is selected", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateRAID()).toBe(false);
    });

    it("returns false if any selected has filesystem", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateRAID()).toBe(false);
    });

    it("returns false if any selected is volume group", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([
        {
          type: "lvm-vg"
        },
        {
          type: "physical"
        }
      ]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateRAID()).toBe(false);
    });

    it("returns false if not super user", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return false;
      };
      expect($scope.canCreateRAID()).toBe(false);
    });

    it("returns true if more than 1 selected", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      spyOn($scope, "isAllStorageDisabled").and.returnValue(false);
      expect($scope.canCreateRAID()).toBe(true);
    });
  });

  describe("createRAID", function() {
    it("does nothing if canCreateRAID returns false", function() {
      makeController();
      spyOn($scope, "canCreateRAID").and.returnValue(false);
      $scope.availableMode = "other";

      $scope.createRAID();
      expect($scope.availableMode).toBe("other");
    });

    it("sets up availableNew", function() {
      makeController();
      spyOn($scope, "canCreateRAID").and.returnValue(true);
      $scope.availableMode = "other";

      // Add md name to create a name after that index.
      var otherRAID = {
        name: "md4"
      };
      node.disks = [otherRAID];

      // Will be set as the devices.
      var disk0 = {
        $selected: true
      };
      var disk1 = {
        $selected: true
      };
      $scope.available = [disk0, disk1];

      $scope.createRAID();
      expect($scope.availableMode).toBe("raid");
      expect($scope.availableNew.name).toBe("md5");
      expect($scope.availableNew.devices).toEqual([disk0, disk1]);
      expect($scope.availableNew.mode.level).toEqual("raid-0");
      expect($scope.availableNew.spares).toEqual([]);
      expect($scope.availableNew.fstype).toBeNull();
      expect($scope.availableNew.mountPoint).toEqual("");
      expect($scope.availableNew.mountOptions).toEqual("");
    });
  });

  describe("getAvailableRAIDModes", function() {
    it("returns empty list if availableNew null", function() {
      makeController();
      $scope.availableNew = null;

      expect($scope.getAvailableRAIDModes()).toEqual([]);
    });

    it("returns empty list if availableNew.devices not defined", function() {
      makeController();
      $scope.availableNew = {};

      expect($scope.getAvailableRAIDModes()).toEqual([]);
    });

    it("returns raid 0 and 1 for 2 disks", function() {
      makeController();
      $scope.availableNew.devices = [{}, {}];

      var modes = $scope.getAvailableRAIDModes();
      expect(modes[0].level).toEqual("raid-0");
      expect(modes[1].level).toEqual("raid-1");
      expect(modes.length).toEqual(2);
    });

    it("returns raid 0,1,5,10 for 3 disks", function() {
      makeController();
      $scope.availableNew.devices = [{}, {}, {}];

      var modes = $scope.getAvailableRAIDModes();
      expect(modes[0].level).toEqual("raid-0");
      expect(modes[1].level).toEqual("raid-1");
      expect(modes[2].level).toEqual("raid-5");
      expect(modes[3].level).toEqual("raid-10");
      expect(modes.length).toEqual(4);
    });

    it("returns raid 0,1,5,6,10 for 4 disks", function() {
      makeController();
      $scope.availableNew.devices = [{}, {}, {}, {}];

      var modes = $scope.getAvailableRAIDModes();
      expect(modes[0].level).toEqual("raid-0");
      expect(modes[1].level).toEqual("raid-1");
      expect(modes[2].level).toEqual("raid-5");
      expect(modes[3].level).toEqual("raid-6");
      expect(modes[4].level).toEqual("raid-10");
      expect(modes.length).toEqual(5);
    });
  });

  describe("getTotalNumberOfAvailableSpares", function() {
    var modes = [
      {
        level: "raid-0",
        min_disks: 2,
        allows_spares: false
      },
      {
        level: "raid-1",
        min_disks: 2,
        allows_spares: true
      },
      {
        level: "raid-5",
        min_disks: 3,
        allows_spares: true
      },
      {
        level: "raid-6",
        min_disks: 4,
        allows_spares: true
      },
      {
        level: "raid-10",
        min_disks: 3,
        allows_spares: true
      }
    ];

    angular.forEach(modes, function(mode) {
      it("returns current result for " + mode.level, function() {
        makeController();
        $scope.availableNew.mode = mode;
        if (!mode.allows_spares) {
          expect($scope.getTotalNumberOfAvailableSpares()).toBe(0);
        } else {
          var count = makeInteger(mode.min_disks, 100);
          var i,
            devices = [];
          for (i = 0; i < count; i++) {
            devices.push({});
          }
          $scope.availableNew.devices = devices;
          expect($scope.getTotalNumberOfAvailableSpares()).toBe(
            count - mode.min_disks
          );
        }
      });
    });
  });

  describe("getNumberOfRemainingSpares", function() {
    it("returns 0 when getTotalNumberOfAvailableSpares returns 0", function() {
      makeController();
      spyOn($scope, "getTotalNumberOfAvailableSpares").and.returnValue(0);

      expect($scope.getNumberOfRemainingSpares()).toBe(0);
    });

    it("returns allowed minus the current number of spares", function() {
      makeController();
      var count = makeInteger(10, 100);
      spyOn($scope, "getTotalNumberOfAvailableSpares").and.returnValue(count);
      var sparesCount = makeInteger(0, count);
      var i,
        spares = [];
      for (i = 0; i < sparesCount; i++) {
        spares.push({});
      }
      $scope.availableNew.spares = spares;

      expect($scope.getNumberOfRemainingSpares()).toBe(count - sparesCount);
    });
  });

  describe("showSparesColumn", function() {
    it(`returns true when getTotalNumberOfAvailableSpares
        greater than 0`, function() {
      makeController();
      spyOn($scope, "getTotalNumberOfAvailableSpares").and.returnValue(1);

      expect($scope.showSparesColumn()).toBe(true);
    });

    it(`returns false when getTotalNumberOfAvailableSpares
        less than 1`, function() {
      makeController();
      spyOn($scope, "getTotalNumberOfAvailableSpares").and.returnValue(0);

      expect($scope.showSparesColumn()).toBe(false);
    });
  });

  describe("RAIDModeChanged", function() {
    it("clears availableNew.spares", function() {
      makeController();
      $scope.availableNew.spares = [{}, {}];

      $scope.RAIDModeChanged();
      expect($scope.availableNew.spares).toEqual([]);
    });
  });

  describe("isActiveRAIDMember", function() {
    it("returns true when disk key not in spares", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];
      $scope.setAsActiveRAIDMember(disk);

      expect($scope.isActiveRAIDMember(disk)).toBe(true);
    });

    it("returns false when disk key in spares", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];
      $scope.setAsSpareRAIDMember(disk);

      expect($scope.isActiveRAIDMember(disk)).toBe(false);
    });
  });

  describe("isSpareRAIDMember", function() {
    it("returns false when disk key not in spares", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];
      $scope.setAsActiveRAIDMember(disk);

      expect($scope.isSpareRAIDMember(disk)).toBe(false);
    });

    it("returns true when disk key in spares", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];
      $scope.setAsSpareRAIDMember(disk);

      expect($scope.isSpareRAIDMember(disk)).toBe(true);
    });
  });

  describe("setAsActiveRAIDMember", function() {
    it("sets the disk as an active RAID member", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];

      $scope.setAsSpareRAIDMember(disk);
      expect($scope.isSpareRAIDMember(disk)).toBe(true);

      $scope.setAsActiveRAIDMember(disk);
      expect($scope.isActiveRAIDMember(disk)).toBe(true);
    });
  });

  describe("setAsSpareRAIDMember", function() {
    it("sets the disk as a spare RAID member", function() {
      makeController();
      var disk = {
        type: "physical",
        block_id: makeInteger()
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk];

      $scope.setAsActiveRAIDMember(disk);
      expect($scope.isActiveRAIDMember(disk)).toBe(true);

      $scope.setAsSpareRAIDMember(disk);
      expect($scope.isSpareRAIDMember(disk)).toBe(true);
    });
  });

  describe("getNewRAIDSize", function() {
    it("gets proper raid-0 size", function() {
      makeController();
      var disk0 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[0];

      expect($scope.getNewRAIDSize()).toBe("2.0 MB");
    });

    it("gets proper raid-0 size using size", function() {
      makeController();
      var disk0 = {
        original: {
          size: 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[0];

      expect($scope.getNewRAIDSize()).toBe("2.0 MB");
    });

    it("gets proper raid-1 size", function() {
      makeController();
      var disk0 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[1];

      expect($scope.getNewRAIDSize()).toBe("1.0 MB");
    });

    it("gets proper raid-5 size", function() {
      makeController();
      var disk0 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk2 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var spare0 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1, disk2, spare0];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[2];
      $scope.setAsSpareRAIDMember(spare0);

      // The 1MB spare causes us to only use 1MB of each active disk.
      expect($scope.getNewRAIDSize()).toBe("2.0 MB");
    });

    it("gets proper raid-6 size", function() {
      makeController();
      var disk0 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk2 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk3 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var spare0 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1, disk2, disk3, spare0];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[3];
      $scope.setAsSpareRAIDMember(spare0);

      // The 1MB spare causes us to only use 1MB of each active disk.
      expect($scope.getNewRAIDSize()).toBe("2.0 MB");
    });

    it("gets proper raid-10 size", function() {
      makeController();
      var disk0 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk1 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var disk2 = {
        original: {
          available_size: 2 * 1000 * 1000
        }
      };
      var spare0 = {
        original: {
          available_size: 1000 * 1000
        }
      };
      $scope.availableNew.spares = [];
      $scope.availableNew.devices = [disk0, disk1, disk2, spare0];
      $scope.availableNew.mode = $scope.getAvailableRAIDModes()[4];
      $scope.setAsSpareRAIDMember(spare0);

      // The 1MB spare causes us to only use 1MB of each active disk.
      expect($scope.getNewRAIDSize()).toBe("1.5 MB");
    });
  });

  describe("createRAIDCanSave", function() {
    it("returns false if isNewDiskNameInvalid returns true", function() {
      makeController();
      $scope.availableNew.mountPoint = "/";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(true);

      expect($scope.createRAIDCanSave()).toBe(false);
    });

    it("returns false if isMountPointInvalid returns true", function() {
      makeController();
      $scope.availableNew.mountPoint = "not/absolute";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(false);

      expect($scope.createRAIDCanSave()).toBe(false);
    });

    it("returns true if both return false", function() {
      makeController();
      $scope.availableNew.mountPoint = "/";
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(false);

      expect($scope.createRAIDCanSave()).toBe(true);
    });
  });

  describe("availableConfirmCreateRAID", function() {
    it("does nothing if createRAIDCanSave returns false", function() {
      makeController();
      spyOn($scope, "createRAIDCanSave").and.returnValue(false);
      var partition0 = {
        type: "partition",
        block_id: makeInteger(0, 10),
        partition_id: makeInteger(0, 10)
      };
      var partition1 = {
        type: "partition",
        block_id: makeInteger(10, 20),
        partition_id: makeInteger(10, 20)
      };
      var disk0 = {
        type: "physical",
        block_id: makeInteger(0, 10)
      };
      var disk1 = {
        type: "physical",
        block_id: makeInteger(10, 20)
      };
      var availableNew = {
        name: makeName("md"),
        mode: {
          level: "raid-1"
        },
        devices: [partition0, partition1, disk0, disk1],
        spares: [],
        fstype: null,
        mountPoint: "",
        mountOptions: ""
      };
      $scope.availableNew = availableNew;
      $scope.setAsSpareRAIDMember(partition0);
      $scope.setAsSpareRAIDMember(disk0);
      spyOn(MachinesManager, "createRAID");

      $scope.availableConfirmCreateRAID();
      expect(MachinesManager.createRAID).not.toHaveBeenCalled();
    });

    it("calls MachinesManager.createRAID", function() {
      makeController();
      spyOn($scope, "createRAIDCanSave").and.returnValue(true);
      var partition0 = {
        type: "partition",
        block_id: makeInteger(0, 10),
        partition_id: makeInteger(0, 10)
      };
      var partition1 = {
        type: "partition",
        block_id: makeInteger(10, 20),
        partition_id: makeInteger(10, 20)
      };
      var disk0 = {
        type: "physical",
        block_id: makeInteger(0, 10)
      };
      var disk1 = {
        type: "physical",
        block_id: makeInteger(10, 20)
      };
      var availableNew = {
        name: makeName("md"),
        mode: {
          level: "raid-1"
        },
        devices: [partition0, partition1, disk0, disk1],
        spares: [],
        fstype: null,
        mountPoint: "",
        mountOptions: ""
      };
      $scope.availableNew = availableNew;
      $scope.setAsSpareRAIDMember(partition0);
      $scope.setAsSpareRAIDMember(disk0);
      spyOn(MachinesManager, "createRAID");

      $scope.availableConfirmCreateRAID();
      expect(MachinesManager.createRAID).toHaveBeenCalledWith(node, {
        name: availableNew.name,
        level: "raid-1",
        block_devices: [disk1.block_id],
        partitions: [partition1.partition_id],
        spare_devices: [disk0.block_id],
        spare_partitions: [partition0.partition_id]
      });
    });

    it("calls MachinesManager.createRAID with filesystem", function() {
      makeController();
      spyOn($scope, "createRAIDCanSave").and.returnValue(true);
      var partition0 = {
        type: "partition",
        block_id: makeInteger(0, 10),
        partition_id: makeInteger(0, 10)
      };
      var partition1 = {
        type: "partition",
        block_id: makeInteger(10, 20),
        partition_id: makeInteger(10, 20)
      };
      var disk0 = {
        type: "physical",
        block_id: makeInteger(0, 10)
      };
      var disk1 = {
        type: "physical",
        block_id: makeInteger(10, 20)
      };
      var availableNew = {
        name: makeName("md"),
        mode: {
          level: "raid-1"
        },
        devices: [partition0, partition1, disk0, disk1],
        spares: [],
        fstype: "ext4",
        mountPoint: makeName("/path"),
        mountOptions: makeName("options")
      };
      $scope.availableNew = availableNew;
      $scope.setAsSpareRAIDMember(partition0);
      $scope.setAsSpareRAIDMember(disk0);
      spyOn(MachinesManager, "createRAID");

      $scope.availableConfirmCreateRAID();
      expect(MachinesManager.createRAID).toHaveBeenCalledWith(node, {
        name: availableNew.name,
        level: "raid-1",
        block_devices: [disk1.block_id],
        partitions: [partition1.partition_id],
        spare_devices: [disk0.block_id],
        spare_partitions: [partition0.partition_id],
        fstype: "ext4",
        mount_point: availableNew.mountPoint,
        mount_options: availableNew.mountOptions
      });
    });
  });

  describe("canCreateVolumeGroup", function() {
    it("returns false isAvailableDisabled returns true", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateVolumeGroup()).toBe(false);
    });

    it("returns false if any selected has filesystem", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(true);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateVolumeGroup()).toBe(false);
    });

    it("returns false if any selected is volume group", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([
        {
          type: "lvm-vg"
        },
        {
          type: "physical"
        }
      ]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateVolumeGroup()).toBe(false);
    });

    it("returns false if not super user", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return false;
      };
      expect($scope.canCreateVolumeGroup()).toBe(false);
    });

    it("returns true if aleast 1 selected", function() {
      makeController();
      spyOn($scope, "isAvailableDisabled").and.returnValue(false);
      spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
      spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
      $scope.canEdit = function() {
        return true;
      };
      expect($scope.canCreateVolumeGroup()).toBe(true);
    });
  });

  describe("createVolumeGroup", function() {
    it("does nothing if canCreateVolumeGroup returns false", function() {
      makeController();
      spyOn($scope, "canCreateVolumeGroup").and.returnValue(false);
      $scope.availableMode = "other";

      $scope.createVolumeGroup();
      expect($scope.availableMode).toBe("other");
    });

    it("sets up availableNew", function() {
      makeController();
      spyOn($scope, "canCreateVolumeGroup").and.returnValue(true);
      $scope.availableMode = "other";

      // Add vg name to create a name after that index.
      var otherVG = {
        name: "vg4"
      };
      node.disks = [otherVG];

      // Will be set as the devices.
      var disk0 = {
        $selected: true
      };
      var disk1 = {
        $selected: true
      };
      $scope.available = [disk0, disk1];

      $scope.createVolumeGroup();
      expect($scope.availableMode).toBe("volume-group");
      expect($scope.availableNew.name).toBe("vg5");
      expect($scope.availableNew.devices).toEqual([disk0, disk1]);
    });
  });

  describe("getNewVolumeGroupSize", function() {
    it("return the total of all devices", function() {
      makeController();
      $scope.availableNew.devices = [
        {
          original: {
            available_size: 1000 * 1000
          }
        },
        {
          original: {
            available_size: 1000 * 1000
          }
        },
        {
          original: {
            available_size: 1000 * 1000
          }
        }
      ];

      expect($scope.getNewVolumeGroupSize()).toBe("3.0 MB");
    });

    it("return the total of all devices using size", function() {
      makeController();
      $scope.availableNew.devices = [
        {
          original: {
            size: 1000 * 1000
          }
        },
        {
          original: {
            size: 1000 * 1000
          }
        },
        {
          original: {
            size: 1000 * 1000
          }
        }
      ];

      expect($scope.getNewVolumeGroupSize()).toBe("3.0 MB");
    });
  });

  describe("createVolumeGroupCanSave", function() {
    it("return true if isNewDiskNameInvalid returns false", function() {
      makeController();
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(false);

      expect($scope.createVolumeGroupCanSave()).toBe(true);
    });

    it("return false if isNewDiskNameInvalid returns true", function() {
      makeController();
      spyOn($scope, "isNewDiskNameInvalid").and.returnValue(true);

      expect($scope.createVolumeGroupCanSave()).toBe(false);
    });
  });

  describe("availableConfirmCreateVolumeGroup", function() {
    it("does nothing if createVolumeGroupCanSave returns false", function() {
      makeController();
      spyOn($scope, "createVolumeGroupCanSave").and.returnValue(false);
      var partition0 = {
        type: "partition",
        block_id: makeInteger(0, 10),
        partition_id: makeInteger(0, 10)
      };
      var partition1 = {
        type: "partition",
        block_id: makeInteger(10, 20),
        partition_id: makeInteger(10, 20)
      };
      var disk0 = {
        type: "physical",
        block_id: makeInteger(0, 10)
      };
      var disk1 = {
        type: "physical",
        block_id: makeInteger(10, 20)
      };
      var availableNew = {
        name: makeName("vg"),
        devices: [partition0, partition1, disk0, disk1]
      };
      $scope.availableNew = availableNew;
      spyOn(MachinesManager, "createVolumeGroup");

      $scope.availableConfirmCreateVolumeGroup();
      expect(MachinesManager.createVolumeGroup).not.toHaveBeenCalled();
    });

    it("calls MachinesManager.createVolumeGroup", function() {
      makeController();
      spyOn($scope, "createVolumeGroupCanSave").and.returnValue(true);
      var partition0 = {
        type: "partition",
        block_id: makeInteger(0, 10),
        partition_id: makeInteger(0, 10)
      };
      var partition1 = {
        type: "partition",
        block_id: makeInteger(10, 20),
        partition_id: makeInteger(10, 20)
      };
      var disk0 = {
        type: "physical",
        block_id: makeInteger(0, 10)
      };
      var disk1 = {
        type: "physical",
        block_id: makeInteger(10, 20)
      };
      var availableNew = {
        name: makeName("vg"),
        devices: [partition0, partition1, disk0, disk1]
      };
      $scope.availableNew = availableNew;
      spyOn(MachinesManager, "createVolumeGroup");

      $scope.availableConfirmCreateVolumeGroup();
      expect(MachinesManager.createVolumeGroup).toHaveBeenCalledWith(node, {
        name: availableNew.name,
        block_devices: [disk0.block_id, disk1.block_id],
        partitions: [partition0.partition_id, partition1.partition_id]
      });
    });
  });

  describe("canAddLogicalVolume", function() {
    it("returns false if not volume group", function() {
      makeController();
      expect(
        $scope.canAddLogicalVolume({
          type: "physical"
        })
      ).toBe(false);
      expect(
        $scope.canAddLogicalVolume({
          type: "virtual"
        })
      ).toBe(false);
      expect(
        $scope.canAddLogicalVolume({
          type: "partition"
        })
      ).toBe(false);
    });

    it("returns false if not enough space", function() {
      makeController();
      expect(
        $scope.canAddLogicalVolume({
          type: "lvm-vg",
          original: {
            available_size: 1.5 * 1024 * 1024
          }
        })
      ).toBe(false);
    });

    it("returns true if enough space", function() {
      makeController();
      expect(
        $scope.canAddLogicalVolume({
          type: "lvm-vg",
          original: {
            available_size: 10 * 1024 * 1024
          }
        })
      ).toBe(true);
    });
  });

  describe("availableLogicalVolume", function() {
    it("sets availableMode to 'logical-volume'", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        available_size_human: "10 GB",
        fstype: null,
        tags: []
      };
      $scope.availableMode = "other";
      $scope.availableLogicalVolume(disk);
      expect($scope.availableMode).toBe("logical-volume");
    });

    it("sets $options to correct values", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        available_size_human: "10 GB",
        fstype: null,
        tags: []
      };
      $scope.availableLogicalVolume(disk);
      expect(disk.$options).toEqual({
        name: "vg0-lv0",
        size: "10",
        sizeUnits: "GB",
        fstype: null,
        tags: []
      });
    });
  });

  describe("isLogicalVolumeNameInvalid", function() {
    it("returns true if doesn't start with volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        $options: {
          name: "v"
        }
      };

      expect($scope.isLogicalVolumeNameInvalid(disk)).toBe(true);
    });

    it("returns true if equal to volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        $options: {
          name: "vg0-"
        }
      };

      expect($scope.isLogicalVolumeNameInvalid(disk)).toBe(true);
    });

    it("returns false has text after the volume group", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        $options: {
          name: "vg0-l"
        }
      };

      expect($scope.isLogicalVolumeNameInvalid(disk)).toBe(false);
    });
  });

  describe("newLogicalVolumeNameChanged", function() {
    it("resets name to volume group name if not present", function() {
      makeController();
      var disk = {
        type: "lvm-vg",
        name: "vg0",
        $options: {
          name: "v"
        }
      };

      $scope.newLogicalVolumeNameChanged(disk);
      expect(disk.$options.name).toBe("vg0-");
    });
  });

  describe("isAddLogicalVolumeSizeInvalid", function() {
    it("returns value from isAddPartitionSizeInvalid", function() {
      makeController();
      var sentinel = {};
      spyOn($scope, "isAddPartitionSizeInvalid").and.returnValue(sentinel);

      expect($scope.isAddLogicalVolumeSizeInvalid({})).toBe(sentinel);
    });
  });

  describe("availableConfirmLogicalVolume", function() {
    it("does nothing if invalid", function() {
      makeController();
      var disk = {
        $options: {
          size: "",
          sizeUnits: "GB"
        }
      };
      spyOn(MachinesManager, "createLogicalVolume");

      $scope.availableConfirmLogicalVolume(disk);

      expect(MachinesManager.createLogicalVolume).not.toHaveBeenCalled();
    });

    it("calls createLogicalVolume with bytes", function() {
      makeController();
      var disk = {
        name: "vg0",
        block_id: makeInteger(0, 100),
        original: {
          available_size: 4 * 1000 * 1000 * 1000,
          available_size_human: "4.0 GB"
        },
        $options: {
          name: "vg0-lv0",
          size: "2",
          sizeUnits: "GB",
          fstype: null,
          mountPoint: "",
          mountOptions: ""
        }
      };
      spyOn(MachinesManager, "createLogicalVolume");

      $scope.availableConfirmLogicalVolume(disk);

      expect(MachinesManager.createLogicalVolume).toHaveBeenCalledWith(
        node,
        disk.block_id,
        "lv0",
        2 * 1000 * 1000 * 1000,
        {}
      );
    });

    it(
      "calls createLogicalVolume with fstype, " +
        "mountPoint, and mountOptions",
      function() {
        makeController();
        var disk = {
          name: "vg0",
          block_id: makeInteger(0, 100),
          original: {
            available_size: 4 * 1000 * 1000 * 1000,
            available_size_human: "4.0 GB"
          },
          $options: {
            name: "vg0-lv0",
            size: "2",
            sizeUnits: "GB",
            fstype: "ext4",
            mountPoint: makeName("/path"),
            mountOptions: makeName("options")
          }
        };
        spyOn(MachinesManager, "createLogicalVolume");

        $scope.availableConfirmLogicalVolume(disk);

        expect(MachinesManager.createLogicalVolume).toHaveBeenCalledWith(
          node,
          disk.block_id,
          "lv0",
          2 * 1000 * 1000 * 1000,
          {
            fstype: "ext4",
            mount_point: disk.$options.mountPoint,
            mount_options: disk.$options.mountOptions
          }
        );
      }
    );

    it("calls createLogicalVolume with available_size bytes", function() {
      makeController();
      var disk = {
        name: "vg0",
        block_id: makeInteger(0, 100),
        original: {
          available_size: 2.6 * 1000 * 1000 * 1000,
          available_size_human: "2.6 GB"
        },
        $options: {
          name: "vg0-lv0",
          size: "2.62",
          sizeUnits: "GB",
          fstype: null,
          mountPoint: "",
          mountOptions: ""
        }
      };
      spyOn(MachinesManager, "createLogicalVolume");

      $scope.availableConfirmLogicalVolume(disk);

      expect(MachinesManager.createLogicalVolume).toHaveBeenCalledWith(
        node,
        disk.block_id,
        "lv0",
        2.6 * 1000 * 1000 * 1000,
        {}
      );
    });

    // regression test for https://bugs.launchpad.net/maas/+bug/1509535
    it(
      "calls createLogicalVolume with available_size bytes" +
        " even when human size gets rounded down",
      function() {
        makeController();
        var disk = {
          name: "vg0",
          block_id: makeInteger(0, 100),
          original: {
            available_size: 2.035 * 1000 * 1000 * 1000,
            available_size_human: "2.0 GB"
          },
          $options: {
            name: "vg0-lv0",
            size: "2.0",
            sizeUnits: "GB",
            fstype: null,
            mountPoint: "",
            mountOptions: ""
          }
        };
        spyOn(MachinesManager, "createLogicalVolume");

        $scope.availableConfirmLogicalVolume(disk);

        expect(MachinesManager.createLogicalVolume).toHaveBeenCalledWith(
          node,
          disk.block_id,
          "lv0",
          2.035 * 1000 * 1000 * 1000,
          {}
        );
      }
    );
  });

  describe("isAllStorageDisabled", function() {
    var RegionConnection, UsersManager, webSocket;
    beforeEach(inject(function($injector) {
      UsersManager = $injector.get("UsersManager");
      RegionConnection = $injector.get("RegionConnection");

      // Mock buildSocket so an actual connection is not made.
      webSocket = new MockWebSocket();
      spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
    }));

    it("false when status is Ready", function() {
      makeController();
      $scope.node.status = "Ready";
      spyOn(UsersManager, "getAuthUser").and.returnValue({
        is_superuser: true
      });
      expect($scope.isAllStorageDisabled()).toBe(false);
    });

    it("false when status is Allocated", function() {
      makeController();
      $scope.node.status = "Allocated";
      spyOn(UsersManager, "getAuthUser").and.returnValue({
        is_superuser: true
      });
      expect($scope.isAllStorageDisabled()).toBe(false);
    });

    it("false when Allocated and owned", function() {
      makeController();
      var user = makeName("user");
      $scope.node.status = "Allocated";
      $scope.node.owner = user;
      spyOn(UsersManager, "getAuthUser").and.returnValue({
        is_superuser: false,
        username: user
      });
      expect($scope.isAllStorageDisabled()).toBe(false);
    });

    it("true when not admin", function() {
      makeController();
      $scope.node.status = "Allocated";
      $scope.node.owner = makeName("user");
      spyOn(UsersManager, "getAuthUser").and.returnValue({
        is_superuser: false,
        username: makeName("user")
      });
      expect($scope.isAllStorageDisabled()).toBe(true);
    });

    it("true otherwise", function() {
      makeController();
      $scope.node.status = makeName("status");
      spyOn(UsersManager, "getAuthUser").and.returnValue({
        is_superuser: true
      });
      expect($scope.isAllStorageDisabled()).toBe(true);
    });
  });

  describe("hasStorageLayoutIssues", function() {
    it("true when node.storage_layout_issues has issues", function() {
      makeController();
      $scope.node.storage_layout_issues = [makeName("issue")];
      expect($scope.hasStorageLayoutIssues()).toBe(true);
    });

    it("false when node.storage_layout_issues has no issues", function() {
      makeController();
      $scope.node.storage_layout_issues = [];
      expect($scope.hasStorageLayoutIssues()).toBe(false);
    });
  });

  describe("openStorageLayoutConfirm", function() {
    it("sets 'confirmStorageLayout' to true", function() {
      makeController();
      $scope.confirmStorageLayout = false;
      $scope.osFamilies = [
        {
          id: "linux",
          name: "Linux",
          layouts: [
            {
              id: "flat",
              name: "Flat"
            },
            {
              id: "lvm",
              name: "LVM"
            },
            {
              id: "bcache",
              name: "bcache"
            },
            {
              id: "vmfs6",
              name: "VMFS6 (VMware ESXI)"
            },
            {
              id: "blank",
              name: "No storage (blank) layout"
            }
          ]
        }
      ];
      $scope.openStorageLayoutConfirm("flat");
      expect($scope.confirmStorageLayout).toBe(true);
    });

    it("sets 'newLayout' to layout argument", function() {
      makeController();
      $scope.osFamilies = [
        {
          id: "linux",
          name: "Linux",
          layouts: [
            {
              id: "flat",
              name: "Flat"
            },
            {
              id: "lvm",
              name: "LVM"
            },
            {
              id: "bcache",
              name: "bcache"
            },
            {
              id: "vmfs6",
              name: "VMFS6 (VMware ESXI)"
            },
            {
              id: "blank",
              name: "No storage (blank) layout"
            }
          ]
        }
      ];
      $scope.openStorageLayoutConfirm("flat");
      expect($scope.newLayout).toEqual($scope.osFamilies[0].layouts[0]);
    });
  });

  describe("closeStorageLayoutConfirm", function() {
    it("sets 'confirmStorageLayout' to false", function() {
      makeController();
      $scope.confirmStorageLayout = true;
      $scope.closeStorageLayoutConfirm();
      expect($scope.confirmStorageLayout).toBe(false);
    });
  });

  describe("updateStorageLayout", function() {
    it("calls 'applyStorageLayout'", function() {
      makeController();
      spyOn(MachinesManager, "applyStorageLayout").and.callFake(function() {
        var deferred = $q.defer();
        return deferred.promise;
      });
      $scope.newLayout = {
        id: "flat",
        name: "Flat"
      };
      $scope.updateStorageLayout($scope.newLayout);
      expect(MachinesManager.applyStorageLayout).toHaveBeenCalled();
    });

    it("calls 'closeStorageLayoutConfirm'", function() {
      makeController();
      spyOn(MachinesManager, "applyStorageLayout").and.callFake(function() {
        var deferred = $q.defer();
        return deferred.promise;
      });
      spyOn($scope, "closeStorageLayoutConfirm");
      $scope.updateStorageLayout({
        id: "flat",
        name: "Flat"
      });
      expect($scope.closeStorageLayoutConfirm).toHaveBeenCalled();
    });
  });

  describe("openNewDatastorePanel", function() {
    it("sets 'createNewDatastore' to true", function() {
      makeController();
      $scope.createNewDatastore = false;
      $scope.available = [
        {
          $selected: true,
          id: 1
        }
      ];
      $scope.openNewDatastorePanel();
      expect($scope.createNewDatastore).toBe(true);
    });

    it("sets newDatastore", function() {
      makeController();
      $scope.available = [
        {
          $selected: true,
          id: 1,
          mount_point: "dev/null",
          size_human: "35 GB"
        }
      ];
      $scope.openNewDatastorePanel();
      expect($scope.datastores.new).toEqual({
        id: $scope.available[0].id,
        name: "",
        mountpoint: $scope.available[0].mount_point,
        filesystem: "VMFS6",
        size: $scope.available[0].size_human
      });
    });
  });

  describe("closeNewDatastorePanel", function() {
    it("sets 'createNewDatastore' to false", function() {
      makeController();
      $scope.createNewDatastore = true;
      $scope.closeNewDatastorePanel();
      expect($scope.createNewDatastore).toBe(false);
    });

    it("sets 'newDatastore' to '{}'", function() {
      makeController();
      $scope.datastores.new = { id: 1, name: "" };
      $scope.closeNewDatastorePanel();
      expect($scope.datastores.new).toEqual({});
    });
  });

  describe("canPerformActionOnDatastoreSet", function() {
    it("return false if not on vmsf6 storage layout", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "flat" };
      expect($scope.canPerformActionOnDatastoreSet()).toBe(false);
    });

    it("return false if already editing datastores", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = true;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "vmfs6" };
      expect($scope.canPerformActionOnDatastoreSet()).toBe(false);
    });

    it("return false if no device is selected", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [];
      $scope.storageLayout = { id: "vmfs6" };
      expect($scope.canPerformActionOnDatastoreSet()).toBe(false);
    });

    it("return true when conditions are matched", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "vmfs6" };
      expect($scope.canPerformActionOnDatastoreSet()).toBe(true);
    });
  });

  describe("canAddToDatastore", function() {
    it("calls 'canPerformActionOnDatastoreSet", function() {
      makeController();
      spyOn($scope, "canPerformActionOnDatastoreSet");
      $scope.canAddToDatastore();
      expect($scope.canPerformActionOnDatastoreSet).toHaveBeenCalled();
    });

    it("return false if not on vmsf6 storage layout", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "flat" };
      $scope.node.disks = [];
      expect($scope.canAddToDatastore()).toBe(false);
    });

    it("return false if already editing datastores", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = true;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "vmfs6" };
      $scope.node.disks = [];
      expect($scope.canAddToDatastore()).toBe(false);
    });

    it("return false if no device is selected", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [];
      $scope.storageLayout = { id: "vmfs6" };
      $scope.node.disks = [];
      expect($scope.canAddToDatastore()).toBe(false);
    });

    it("return false when there are no datastores", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [];
      $scope.storageLayout = { id: "vmfs6" };
      $scope.node.disks = [];
      expect($scope.canAddToDatastore()).toBe(false);
    });

    it("return true when conditions are matched", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.createNewDatastore = false;
      $scope.selectedAvailableDatastores = [1];
      $scope.storageLayout = { id: "vmfs6" };
      $scope.node.disks = [{ parent_type: "vmfs6" }];
      expect($scope.canAddToDatastore()).toBe(true);
    });
  });

  describe("checkAddToDatastoreValid", function() {
    it("selected disks are valid when that condition is true", function() {
      makeController();
      var selected = {
        has_partitions: false
      };
      spyOn($scope, "getSelectedAvailable").and.returnValue([selected]);
      expect($scope.addToDatastoreValid).toBe(false);
      $scope.checkAddToDatastoreValid();
      expect($scope.addToDatastoreValid).toBe(true);
    });

    it("selected disks are not valid disk has a partition", function() {
      makeController();
      var selected = {
        has_partitions: true
      };
      spyOn($scope, "getSelectedAvailable").and.returnValue([selected]);
      expect($scope.addToDatastoreValid).toBe(false);
      $scope.checkAddToDatastoreValid();
      expect($scope.addToDatastoreValid).toBe(false);
    });

    it("selected disks are not valid when no selected disks", function() {
      makeController();
      spyOn($scope, "getSelectedAvailable").and.returnValue([]);
      expect($scope.addToDatastoreValid).toBe(false);
      $scope.checkAddToDatastoreValid();
      expect($scope.addToDatastoreValid).toBe(false);
    });
  });

  describe("openAddToExistingDatastorePanel", function() {
    it("sets 'addToExistingDatastore' to true", function() {
      makeController();
      $scope.addToExistingDatastore = false;
      $scope.available = [
        {
          $selected: true,
          id: 1
        }
      ];
      $scope.openAddToExistingDatastorePanel();
      expect($scope.addToExistingDatastore).toBe(true);
    });

    it("sets 'selectedAvailableDatastores' to selected", function() {
      makeController();
      $scope.datastores.old = [
        {
          $selected: true,
          id: 1
        }
      ];
      $scope.openAddToExistingDatastorePanel();
      expect($scope.selectedAvailableDatastores).toEqual($scope.available);
    });

    it("sets 'datastores.old' to first disk", function() {
      makeController();
      $scope.openAddToExistingDatastorePanel();
      expect($scope.datastores.old).toBe($scope.node.disks[0]);
    });
  });

  describe("closeAddToExistingDatastorePanel", function() {
    it("sets 'addToExistingDatastore' to false", function() {
      makeController();
      $scope.addToExistingDatastore = true;
      $scope.closeAddToExistingDatastorePanel();
      expect($scope.addToExistingDatastore).toBe(false);
    });

    it("sets, 'newDatasore' to '{}'", function() {
      makeController();
      $scope.datastores.new = { id: 1, name: "" };
      $scope.closeAddToExistingDatastorePanel();
      expect($scope.datastores.new).toEqual({});
    });
  });

  describe("createDatastore", function() {
    it("sets 'createNewDatastore' to true", function() {
      makeController();
      spyOn(MachinesManager, "createDatastore").and.callFake(function() {
        var deferred = $q.defer();
        return deferred.promise;
      });
      $scope.createNewDatastore = false;
      $scope.createDatastore();
      expect($scope.createNewDatastore).toBe(true);
    });

    it("calls 'MachinesManager.createDatastore'", function() {
      makeController();
      spyOn(MachinesManager, "createDatastore").and.callFake(function() {
        var deferred = $q.defer();
        return deferred.promise;
      });
      $scope.createDatastore();
      expect(MachinesManager.createDatastore).toHaveBeenCalled();
    });
  });

  describe("getRemoveDatastoreWarningText", function() {
    it("returns correct string if more datastores exist", function() {
      makeController();
      var disks = [
        {
          parent_type: "vmfs6"
        },
        {
          parent_type: "vmfs6"
        },
        {}
      ];
      expect($scope.getRemoveDatastoreWarningText(disks)).toBe(
        "Are you sure you want to remove this datastore?"
      );
    });

    it("returns correct string if last datastore", function() {
      makeController();
      var disks = [
        {
          parent_type: "vmfs6"
        },
        {}
      ];
      expect($scope.getRemoveDatastoreWarningText(disks)).toBe(
        "Are you sure you want to remove this datastore? " +
          "ESXi requires at least one VMFS datastore to deploy."
      );
    });
  });

  describe("getTotalDiskSize", function() {
    it("returns total disk size", function() {
      makeController();
      var disks = [
        {
          size: 2000000
        },
        {
          size: 1000000
        }
      ];
      expect($scope.getTotalDiskSize(disks)).toBe(3000000);
    });
  });

  describe("getFormattedTotalDiskSize", function() {
    it("returns formatted string in MB", function() {
      makeController();
      var disks = [
        {
          size: 1000000
        },
        {
          size: 2000000
        }
      ];
      expect($scope.getFormattedTotalDiskSize(disks)).toBe("3 MB");
    });

    it("returns formatted string in GB", function() {
      makeController();
      var disks = [
        {
          size: 1000000000
        },
        {
          size: 2000000000
        }
      ];
      expect($scope.getFormattedTotalDiskSize(disks)).toBe("3 GB");
    });

    it("returns formtted string in TB", function() {
      makeController();
      var disks = [
        {
          size: 1000000000000
        },
        {
          size: 2000000000000
        }
      ];
      expect($scope.getFormattedTotalDiskSize(disks)).toBe("3.00 TB");
    });
  });
});
