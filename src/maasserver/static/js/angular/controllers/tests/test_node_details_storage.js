/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeStorageController.
 */

describe("NodeStorageController", function() {
    // Load the MAAS module.
    beforeEach(module("MAAS"));

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
    var NodesManager;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
    }));

    // Create the node and functions that will be called on the parent.
    var node, updateNodeSpy, canEditSpy;
    beforeEach(function() {
        node = {
            disks: []
        };
        updateNodeSpy = jasmine.createSpy("updateNode");
        canEditSpy = jasmine.createSpy("canEdit");
        $parentScope.node = node;
        $parentScope.updateNode = updateNodeSpy;
        $parentScope.canEdit = canEditSpy;
    });

    // Makes the NodeStorageController
    function makeController() {
        // Create the controller.
        var controller = $controller("NodeStorageController", {
            $scope: $scope,
            NodesManager: NodesManager
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
                partitions: null
            },
            {
                // Disk with filesystem, no mount point
                id: 1,
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
                    is_format_fstype: true,
                    fstype: "ext4",
                    mount_point: null
                    },
                partitions: null
            },
            {
                // Disk with mounted filesystem
                id: 2,
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
                    is_format_fstype: true,
                    fstype: "ext4",
                    mount_point: "/"
                    },
                partitions: null
            },
            {
                // Partitioned disk, one partition free one used
                id: 3,
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
                            is_format_fstype: true,
                            fstype: "ext4",
                            mount_point: "/mnt"
                        },
                        used_for: "ext4 formatted filesystem mounted at /mnt."
                    }
                ]
            }
        ];
    }

    it("sets initial values", function() {
        var controller = makeController();
        expect($scope.editing).toBe(false);
        expect($scope.column).toBe('model');
        expect($scope.has_disks).toBe(false);
        expect($scope.filesystems).toEqual([]);
        expect($scope.filesystemsMap).toEqual({});
        expect($scope.filesystemMode).toBeNull();
        expect($scope.filesystemAllSelected).toBe(false);
        expect($scope.available).toEqual([]);
        expect($scope.availableMap).toEqual({});
        expect($scope.availableMode).toBeNull();
        expect($scope.availableAllSelected).toBe(false);
        expect($scope.used).toEqual([]);
    });

    it("starts watching disks once nodeLoaded called", function() {
        var controller = makeController();

        spyOn($scope, "$watch");
        $scope.nodeLoaded();

        var watches = [];
        var i, calls = $scope.$watch.calls.allArgs();
        for(i = 0; i < calls.length; i++) {
            watches.push(calls[i][0]);
        }

        expect(watches).toEqual(["node.disks"]);
    });

    it("disks updated once nodeLoaded called", function() {
        var disks = makeDisks();
        node.disks = disks;

        var filesystems = [
            {
                name: disks[2].name,
                size_human: disks[2].size_human,
                fstype: disks[2].filesystem.fstype,
                mount_point: disks[2].filesystem.mount_point,
                block_id: disks[2].id,
                partition_id: null,
                $selected: false
            },
            {
                name: disks[3].partitions[1].name,
                size_human: disks[3].partitions[1].size_human,
                fstype: disks[3].partitions[1].filesystem.fstype,
                mount_point: disks[3].partitions[1].filesystem.mount_point,
                block_id: disks[3].id,
                partition_id: disks[3].partitions[1].id,
                $selected: false
            }
        ];
        var available = [
            {
                name: disks[0].name,
                size_human: disks[0].size_human,
                used_size_human: disks[0].used_size_human,
                type: disks[0].type,
                model: disks[0].model,
                serial: disks[0].serial,
                tags: disks[0].tags,
                fstype: null,
                mount_point: null,
                block_id: 0,
                partition_id: null,
                has_partitions: false,
                $selected: false,
                $options: {}
            },
            {
                name: disks[1].name,
                size_human: disks[1].available_size_human,
                used_size_human: disks[1].used_size_human,
                type: disks[1].type,
                model: disks[1].model,
                serial: disks[1].serial,
                tags: disks[1].tags,
                fstype: "ext4",
                mount_point: null,
                block_id: 1,
                partition_id: null,
                has_partitions: false,
                $selected: false,
                $options: {}
            },
            {
                name: disks[3].partitions[0].name,
                size_human: disks[3].size_human,
                used_size_human: disks[3].used_size_human,
                type: disks[3].partitions[0].type,
                model: "",
                serial: "",
                tags: [],
                fstype: null,
                mount_point: null,
                block_id: 3,
                partition_id: 0,
                has_partitions: false,
                $selected: false,
                $options: {}
            }
        ];
        var used = [
            {
                name: disks[2].name,
                type: disks[2].type,
                model: disks[2].model,
                serial: disks[2].serial,
                tags: disks[2].tags,
                used_for: disks[2].used_for
            },
            {
                name: disks[3].name,
                type: disks[3].type,
                model: disks[3].model,
                serial: disks[3].serial,
                tags: disks[3].tags,
                used_for: disks[3].used_for
            },
            {
                name: disks[3].partitions[1].name,
                type: "partition",
                model: "",
                serial: "",
                tags: [],
                used_for: disks[3].partitions[1].used_for
            }
        ];
        var controller = makeController();
        $scope.nodeLoaded();
        $rootScope.$digest();
        expect($scope.has_disks).toEqual(true);
        expect($scope.filesystems).toEqual(filesystems);
        expect($scope.available).toEqual(available);
        expect($scope.used).toEqual(used);
    });

    it("disks $selected and $options not lost on update", function() {
        var controller = makeController();
        var disks = makeDisks();
        node.disks = disks;

        // Load the filesystems, available, and used once.
        $scope.nodeLoaded();
        $rootScope.$digest();

        // Set all filesystems and available to selected.
        angular.forEach($scope.filesystems, function(filesystem) {
            filesystem.$selected = true;
        });
        angular.forEach($scope.available, function(disk) {
            disk.$selected = true;
        });

        // Get all the options for available.
        var options = [];
        angular.forEach($scope.available, function(disk) {
            options.push(disk.$options);
        });

        // Force the disks to change so the filesystems, available, and used
        // are reloaded.
        var firstFilesystem = $scope.filesystems[0];
        node.disks = angular.copy(node.disks);
        $rootScope.$digest();
        expect($scope.filesystems[0]).not.toBe(firstFilesystem);
        expect($scope.filesystems[0]).toEqual(firstFilesystem);

        // All filesystems and available should be selected.
        angular.forEach($scope.filesystems, function(filesystem) {
            expect(filesystem.$selected).toBe(true);
        });
        angular.forEach($scope.available, function(disk) {
            expect(disk.$selected).toBe(true);
        });

        // All available should have the same options.
        angular.forEach($scope.available, function(disk, idx) {
            expect(disk.$options).toBe(options[idx]);
        });
    });

    describe("getSelectedFilesystems", function() {

        it("returns selected filesystems", function() {
            var controller = makeController();
            var filesystems = [
                { $selected: true },
                { $selected: true },
                { $selected: false },
                { $selected: false }
            ];
            $scope.filesystems = filesystems;
            expect($scope.getSelectedFilesystems()).toEqual(
                [filesystems[0], filesystems[1]]);
        });
    });

    describe("updateFilesystemSelection", function() {

        it("sets filesystemMode to NONE when none selected", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedFilesystems").and.returnValue([]);
            $scope.filesystemMode = "other";

            $scope.updateFilesystemSelection();

            expect($scope.filesystemMode).toBeNull();
        });

        it("doesn't sets filesystemMode to SINGLE when not force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
            $scope.filesystemMode = "other";

            $scope.updateFilesystemSelection();

            expect($scope.filesystemMode).toBe("other");
        });

        it("sets filesystemMode to SINGLE when force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
            $scope.filesystemMode = "other";

            $scope.updateFilesystemSelection(true);

            expect($scope.filesystemMode).toBe("single");
        });

        it("doesn't sets filesystemMode to MUTLI when not force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedFilesystems").and.returnValue([{}, {}]);
            $scope.filesystemMode = "other";

            $scope.updateFilesystemSelection();

            expect($scope.filesystemMode).toBe("other");
        });

        it("sets filesystemMode to MULTI when force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedFilesystems").and.returnValue([{}, {}]);
            $scope.filesystemMode = "other";

            $scope.updateFilesystemSelection(true);

            expect($scope.filesystemMode).toBe("multi");
        });

        it("sets filesystemAllSelected to false when none selected",
            function() {
                var controller = makeController();
                spyOn($scope, "getSelectedFilesystems").and.returnValue([]);
                $scope.filesystemAllSelected = true;

                $scope.updateFilesystemSelection();

                expect($scope.filesystemAllSelected).toBe(false);
            });

        it("sets filesystemAllSelected to false when not all selected",
            function() {
                var controller = makeController();
                $scope.filesystems = [{}, {}];
                spyOn($scope, "getSelectedFilesystems").and.returnValue([{}]);
                $scope.filesystemAllSelected = true;

                $scope.updateFilesystemSelection();

                expect($scope.filesystemAllSelected).toBe(false);
            });

        it("sets filesystemAllSelected to true when all selected",
            function() {
                var controller = makeController();
                $scope.filesystems = [{}, {}];
                spyOn($scope, "getSelectedFilesystems").and.returnValue(
                    [{}, {}]);
                $scope.filesystemAllSelected = false;

                $scope.updateFilesystemSelection();

                expect($scope.filesystemAllSelected).toBe(true);
            });
    });

    describe("toggleFilesystemSelect", function() {

        it("inverts $selected", function() {
            var controller = makeController();
            var filesystem = { $selected: true };
            spyOn($scope, "updateFilesystemSelection");

            $scope.toggleFilesystemSelect(filesystem);

            expect(filesystem.$selected).toBe(false);
            $scope.toggleFilesystemSelect(filesystem);
            expect(filesystem.$selected).toBe(true);
            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("toggleFilesystemAllSelect", function() {

        it("sets all to true if not all selected", function() {
            var controller = makeController();
            var filesystems = [{ $selected: true }, { $selected: false }];
            $scope.filesystems = filesystems;
            $scope.filesystemAllSelected = false;
            spyOn($scope, "updateFilesystemSelection");

            $scope.toggleFilesystemAllSelect();

            expect(filesystems[0].$selected).toBe(true);
            expect(filesystems[1].$selected).toBe(true);
            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(
                true);
        });

        it("sets all to false if all selected", function() {
            var controller = makeController();
            var filesystems = [{ $selected: true }, { $selected: true }];
            $scope.filesystems = filesystems;
            $scope.filesystemAllSelected = true;
            spyOn($scope, "updateFilesystemSelection");

            $scope.toggleFilesystemAllSelect();

            expect(filesystems[0].$selected).toBe(false);
            expect(filesystems[1].$selected).toBe(false);
            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("isFilesystemsDisabled", function() {

        it("returns false for NONE", function() {
            var controller = makeController();
            $scope.filesystemMode = null;

            expect($scope.isFilesystemsDisabled()).toBe(false);
        });

        it("returns false for SINGLE", function() {
            var controller = makeController();
            $scope.filesystemMode = "single";

            expect($scope.isFilesystemsDisabled()).toBe(false);
        });

        it("returns false for MULTI", function() {
            var controller = makeController();
            $scope.filesystemMode = "multi";

            expect($scope.isFilesystemsDisabled()).toBe(false);
        });

        it("returns true for UNMOUNT", function() {
            var controller = makeController();
            $scope.filesystemMode = "unmount";

            expect($scope.isFilesystemsDisabled()).toBe(true);
        });
    });

    describe("filesystemCancel", function() {

        it("calls updateFilesystemSelection with force true", function() {
            var controller = makeController();
            spyOn($scope, "updateFilesystemSelection");

            $scope.filesystemCancel();

            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("filesystemUnmount", function() {

        it("sets filesystemMode to UNMOUNT", function() {
            var controller = makeController();
            $scope.filesystemMode = "other";

            $scope.filesystemUnmount();

            expect($scope.filesystemMode).toBe("unmount");
        });
    });

    describe("quickFilesystemUnmount", function() {

        it("selects filesystem and calls filesystemUnmount", function() {
            var controller = makeController();
            var filesystems = [{ $selected: true }, { $selected: false }];
            $scope.filesystems = filesystems;
            spyOn($scope, "updateFilesystemSelection");
            spyOn($scope, "filesystemUnmount");

            $scope.quickFilesystemUnmount(filesystems[1]);

            expect(filesystems[0].$selected).toBe(false);
            expect(filesystems[1].$selected).toBe(true);
            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith(
                true);
            expect($scope.filesystemUnmount).toHaveBeenCalled();
        });
    });

    describe("filesystemConfirmUnmount", function() {

        it("calls NodesManager.updateFilesystem", function() {
            var controller = makeController();
            var filesystem = {
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100),
                fstype: makeName("fs")
            };
            $scope.filesystems = [filesystem];
            spyOn(NodesManager, "updateFilesystem");
            spyOn($scope, "updateFilesystemSelection");

            $scope.filesystemConfirmUnmount(filesystem);

            expect(NodesManager.updateFilesystem).toHaveBeenCalledWith(
                node, filesystem.block_id, filesystem.partition_id,
                filesystem.fstype, null);
        });

        it("removes filesystem from filesystems", function() {
            var controller = makeController();
            var filesystem = {
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100),
                fstype: makeName("fs")
            };
            $scope.filesystems = [filesystem];
            spyOn(NodesManager, "updateFilesystem");
            spyOn($scope, "updateFilesystemSelection");

            $scope.filesystemConfirmUnmount(filesystem);

            expect($scope.filesystems).toEqual([]);
            expect($scope.updateFilesystemSelection).toHaveBeenCalledWith();
        });
    });

    describe("hasUnmountedFilesystem", function() {

        it("returns false if no fstype", function() {
            var controller = makeController();
            var disk = {
                fstype: null
            };

            expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
        });

        it("returns false if empty fstype", function() {
            var controller = makeController();
            var disk = {
                fstype: ""
            };

            expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
        });

        it("returns true if no mount_point", function() {
            var controller = makeController();
            var disk = {
                fstype: "ext4",
                mount_point: null
            };

            expect($scope.hasUnmountedFilesystem(disk)).toBe(true);
        });

        it("returns true if empty mount_point", function() {
            var controller = makeController();
            var disk = {
                fstype: "ext4",
                mount_point: ""
            };

            expect($scope.hasUnmountedFilesystem(disk)).toBe(true);
        });

        it("returns false if has mount_point", function() {
            var controller = makeController();
            var disk = {
                fstype: "ext4",
                mount_point: "/"
            };

            expect($scope.hasUnmountedFilesystem(disk)).toBe(false);
        });
    });

    describe("getSize", function() {

        it("returns used size if unmounted filesystem", function() {
            var controller = makeController();
            var used_size = {};
            var size = {};
            var disk = {
                used_size_human: used_size,
                size_human: size
            };
            spyOn($scope, "hasUnmountedFilesystem").and.returnValue(true);

            expect($scope.getSize(disk)).toBe(used_size);
        });

        it("returns size if mounted filesystem", function() {
            var controller = makeController();
            var used_size = {};
            var size = {};
            var disk = {
                used_size_human: used_size,
                size_human: size
            };
            spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);

            expect($scope.getSize(disk)).toBe(size);
        });
    });

    describe("getDeviceType", function() {

        it("returns logical volume", function() {
            var controller = makeController();
            var disk = {
                type: "virtual",
                parent_type: "lvm-vg"
            };

            expect($scope.getDeviceType(disk)).toBe("Logical Volume");
        });

        it("returns parent_type", function() {
            var controller = makeController();
            var disk = {
                type: "virtual",
                parent_type: "raid0"
            };

            expect($scope.getDeviceType(disk)).toBe("Raid0");
        });

        it("returns volume group", function() {
            var controller = makeController();
            var disk = {
                type: "lvm-vg"
            };

            expect($scope.getDeviceType(disk)).toBe("Volume Group");
        });

        it("returns type", function() {
            var controller = makeController();
            var disk = {
                type: "physical"
            };

            expect($scope.getDeviceType(disk)).toBe("Physical");
        });
    });

    describe("getSelectedAvailable", function() {

        it("returns selected available", function() {
            var controller = makeController();
            var available = [
                { $selected: true },
                { $selected: true },
                { $selected: false },
                { $selected: false }
            ];
            $scope.available = available;
            expect($scope.getSelectedAvailable()).toEqual(
                [available[0], available[1]]);
        });
    });

    describe("updateAvailableSelection", function() {

        it("sets availableMode to NONE when none selected", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedAvailable").and.returnValue([]);
            $scope.availableMode = "other";

            $scope.updateAvailableSelection();

            expect($scope.availableMode).toBeNull();
        });

        it("doesn't sets availableMode to SINGLE when not force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
            $scope.availableMode = "other";

            $scope.updateAvailableSelection();

            expect($scope.availableMode).toBe("other");
        });

        it("sets availableMode to SINGLE when force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
            $scope.availableMode = "other";

            $scope.updateAvailableSelection(true);

            expect($scope.availableMode).toBe("single");
        });

        it("doesn't sets availableMode to MUTLI when not force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
            $scope.availableMode = "other";

            $scope.updateAvailableSelection();

            expect($scope.availableMode).toBe("other");
        });

        it("sets availableMode to MULTI when force", function() {
            var controller = makeController();
            spyOn($scope, "getSelectedAvailable").and.returnValue([{}, {}]);
            $scope.availableMode = "other";

            $scope.updateAvailableSelection(true);

            expect($scope.availableMode).toBe("multi");
        });

        it("sets availableAllSelected to false when none selected",
            function() {
                var controller = makeController();
                spyOn($scope, "getSelectedAvailable").and.returnValue([]);
                $scope.availableAllSelected = true;

                $scope.updateAvailableSelection();

                expect($scope.availableAllSelected).toBe(false);
            });

        it("sets availableAllSelected to false when not all selected",
            function() {
                var controller = makeController();
                $scope.available = [{}, {}];
                spyOn($scope, "getSelectedAvailable").and.returnValue([{}]);
                $scope.availableAllSelected = true;

                $scope.updateAvailableSelection();

                expect($scope.availableAllSelected).toBe(false);
            });

        it("sets availableAllSelected to true when all selected",
            function() {
                var controller = makeController();
                $scope.available = [{}, {}];
                spyOn($scope, "getSelectedAvailable").and.returnValue(
                    [{}, {}]);
                $scope.availableAllSelected = false;

                $scope.updateAvailableSelection();

                expect($scope.availableAllSelected).toBe(true);
            });
    });

    describe("toggleAvailableSelect", function() {

        it("inverts $selected", function() {
            var controller = makeController();
            var disk = { $selected: true };
            spyOn($scope, "updateAvailableSelection");

            $scope.toggleAvailableSelect(disk);

            expect(disk.$selected).toBe(false);
            $scope.toggleAvailableSelect(disk);
            expect(disk.$selected).toBe(true);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("toggleAvailableAllSelect", function() {

        it("sets all to true if not all selected", function() {
            var controller = makeController();
            var available = [{ $selected: true }, { $selected: false }];
            $scope.available = available;
            $scope.availableAllSelected = false;
            spyOn($scope, "updateAvailableSelection");

            $scope.toggleAvailableAllSelect();

            expect(available[0].$selected).toBe(true);
            expect(available[1].$selected).toBe(true);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("sets all to false if all selected", function() {
            var controller = makeController();
            var available = [{ $selected: true }, { $selected: true }];
            $scope.available = available;
            $scope.availableAllSelected = true;
            spyOn($scope, "updateAvailableSelection");

            $scope.toggleAvailableAllSelect();

            expect(available[0].$selected).toBe(false);
            expect(available[1].$selected).toBe(false);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("isAvailableDisabled", function() {

        it("returns false for NONE", function() {
            var controller = makeController();
            $scope.availableMode = null;

            expect($scope.isAvailableDisabled()).toBe(false);
        });

        it("returns false for SINGLE", function() {
            var controller = makeController();
            $scope.availableMode = "single";

            expect($scope.isAvailableDisabled()).toBe(false);
        });

        it("returns false for MULTI", function() {
            var controller = makeController();
            $scope.availableMode = "multi";

            expect($scope.isAvailableDisabled()).toBe(false);
        });

        it("returns true for UNMOUNT", function() {
            var controller = makeController();
            $scope.availableMode = "unmount";

            expect($scope.isAvailableDisabled()).toBe(true);
        });
    });

    describe("canFormatAndMount", function() {

        it("returns false if lvm-vg", function() {
            var controller = makeController();
            var disk = { type: "lvm-vg" };
            expect($scope.canFormatAndMount(disk)).toBe(false);
        });

        it("returns false if has_partitions", function() {
            var controller = makeController();
            var disk = { type: "physical", has_partitions: true };
            expect($scope.canFormatAndMount(disk)).toBe(false);
        });

        it("returns true otherwise", function() {
            var controller = makeController();
            var disk = { type: "physical", has_partitions: false };
            expect($scope.canFormatAndMount(disk)).toBe(true);
        });
    });

    describe("getFormatAndMountButtonText", function() {

        it("returns Mount if umounted filesystem", function() {
            var controller = makeController();
            spyOn($scope, "hasUnmountedFilesystem").and.returnValue(true);
            expect($scope.getFormatAndMountButtonText({})).toBe("Mount");
        });

        it("returns Format if not formatted filesystem", function() {
            var controller = makeController();
            spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);
            expect($scope.getFormatAndMountButtonText({})).toBe("Format");
        });
    });

    describe("getPartitionButtonText", function() {

        it("returns Add Partition if already has partitions", function() {
            var controller = makeController();
            expect($scope.getPartitionButtonText({
                has_partitions: true
            })).toBe("Add Partition");
        });

        it("returns Partition if no partitions", function() {
            var controller = makeController();
            expect($scope.getPartitionButtonText({
                has_partitions: false
            })).toBe("Partition");
        });
    });

    describe("canAddPartition", function() {

        it("returns false if partition", function() {
            var controller = makeController();
            expect($scope.canAddPartition({
                type: "partition"
            })).toBe(false);
        });

        it("returns false if lvm-vg", function() {
            var controller = makeController();
            expect($scope.canAddPartition({
                type: "lvm-vg"
            })).toBe(false);
        });

        it("returns false if logical volume", function() {
            var controller = makeController();
            expect($scope.canAddPartition({
                type: "virtual",
                parent_type: "lvm-vg"
            })).toBe(false);
        });

        it("returns false if formatted", function() {
            var controller = makeController();
            expect($scope.canAddPartition({
                type: "physical",
                fstype: "ext4"
            })).toBe(false);
        });

        it("returns true otherwise", function() {
            var controller = makeController();
            expect($scope.canAddPartition({
                type: "physical",
                fstype: ""
            })).toBe(true);
        });
    });

    describe("availableCancel", function() {

        it("calls updateAvailableSelection with force true", function() {
            var controller = makeController();
            spyOn($scope, "updateAvailableSelection");

            $scope.availableCancel();

            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("availableUnformat", function() {

        it("sets filesystemMode to UNFORMAT", function() {
            var controller = makeController();
            $scope.availableMode = "other";

            $scope.availableUnformat();

            expect($scope.availableMode).toBe("unformat");
        });
    });

    describe("availableConfirmUnformat", function() {

        it("calls NodesManager.updateFilesystem", function() {
            var controller = makeController();
            var disk = {
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100)
            };
            spyOn(NodesManager, "updateFilesystem");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmUnformat(disk);

            expect(NodesManager.updateFilesystem).toHaveBeenCalledWith(
                node, disk.block_id, disk.partition_id,
                null, null);
        });

        it("clears fstype and sets used_size to size", function() {
            var controller = makeController();
            var disk = {
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100),
                fstype: "ext4",
                size_human: makeName("size"),
                used_size_human: makeName("used_size")
            };
            spyOn(NodesManager, "updateFilesystem");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmUnformat(disk);

            expect(disk.fstype).toBeNull();
            expect(disk.size_human).toBe(disk.used_size_human);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("availableFormatAndMount", function() {

        it("sets default $options", function() {
            var controller = makeController();
            var disk = {};

            $scope.availableFormatAndMount(disk);

            expect(disk.$options).toEqual({
                fstype: "ext4",
                mount_point: ""
            });
        });

        it("sets $options with disk values", function() {
            var controller = makeController();
            var disk = {
                fstype: makeName("fs"),
                mount_point: makeName("mount")
            };

            $scope.availableFormatAndMount(disk);

            expect(disk.$options).toEqual({
                fstype: disk.fstype,
                mount_point: disk.mount_point
            });
        });

        it("sets availableMode to FORMAT_AND_MOUNT", function() {
            var controller = makeController();
            var disk = {};

            $scope.availableFormatAndMount(disk);

            expect($scope.availableMode).toBe("format-mount");
        });
    });

    describe("availableQuickFormatAndMount", function() {

        it("selects disks and deselects others", function() {
            var controller = makeController();
            var available = [{ $selected: false }, { $selected: true }];
            $scope.available = available;
            spyOn($scope, "updateAvailableSelection");
            spyOn($scope, "availableFormatAndMount");

            $scope.availableQuickFormatAndMount(available[0]);

            expect(available[0].$selected).toBe(true);
            expect(available[1].$selected).toBe(false);
        });

        it("calls updateAvailableSelection with force true", function() {
            var controller = makeController();
            var available = [{ $selected: false }, { $selected: true }];
            spyOn($scope, "updateAvailableSelection");
            spyOn($scope, "availableFormatAndMount");

            $scope.availableQuickFormatAndMount(available[0]);

            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("calls availableFormatAndMount with disk", function() {
            var controller = makeController();
            var available = [{ $selected: false }, { $selected: true }];
            spyOn($scope, "updateAvailableSelection");
            spyOn($scope, "availableFormatAndMount");

            $scope.availableQuickFormatAndMount(available[0]);

            expect($scope.availableFormatAndMount).toHaveBeenCalledWith(
                available[0]);
        });
    });

    describe("getAvailableFormatSubmitText", function() {

        it("returns 'Format & Mount' when mount_point set", function() {
            var controller = makeController();
            var disk = {
                $options: {
                    mount_point: "/"
                }
            };

            expect($scope.getAvailableFormatSubmitText(disk)).toBe(
                "Format & Mount");
        });

        it("returns 'Format' when mount_point is null", function() {
            var controller = makeController();
            var disk = {
                $options: {
                    mount_point: null
                }
            };

            expect($scope.getAvailableFormatSubmitText(disk)).toBe(
                "Format");
        });

        it("returns 'Format' when mount_point is empty", function() {
            var controller = makeController();
            var disk = {
                $options: {
                    mount_point: ""
                }
            };

            expect($scope.getAvailableFormatSubmitText(disk)).toBe(
                "Format");
        });
    });

    describe("availableConfirmFormatAndMount", function() {

        it("does nothing when isMountPointInvalid returns true", function() {
            var controller = makeController();
            var disk = {
                $options: {
                    mount_point: "invalid"
                }
            };
            spyOn($scope, "isMountPointInvalid").and.returnValue(true);
            spyOn(NodesManager, "updateFilesystem");

            $scope.availableConfirmFormatAndMount(disk);
            expect(NodesManager.updateFilesystem).not.toHaveBeenCalled();
        });

        it("calls NodesManager.updateFilesystem with fstype and mount_point",
            function() {
                var controller = makeController();
                var disk = {
                    block_id: makeInteger(0, 100),
                    partition_id: makeInteger(0, 100),
                    $options: {
                        fstype: makeName("fs"),
                        mount_point: makeName("/path")
                    }
                };
                spyOn(NodesManager, "updateFilesystem");

                $scope.availableConfirmFormatAndMount(disk);
                expect(NodesManager.updateFilesystem).toHaveBeenCalledWith(
                    node, disk.block_id, disk.partition_id,
                    disk.$options.fstype, disk.$options.mount_point);
            });

        it("sets new values on disk and sets size to used_size", function() {
            var controller = makeController();
            var disk = {
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100),
                size_human: makeName("size"),
                used_size_human: makeName("used_size"),
                $options: {
                    fstype: makeName("fs"),
                    mount_point: makeName("/path")
                }
            };
            spyOn(NodesManager, "updateFilesystem");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmFormatAndMount(disk);
            expect(disk.fstype).toBe(disk.$options.fstype);
            expect(disk.mount_point).toBe(disk.$options.mount_point);
            expect(disk.size_human).toBe(disk.used_size_human);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("moves disks to filesystems list", function() {
            var controller = makeController();
            var disk = {
                name: makeName("name"),
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100),
                size_human: makeName("size"),
                used_size_human: makeName("used_size"),
                $options: {
                    fstype: makeName("fs"),
                    mount_point: makeName("/path")
                }
            };
            spyOn(NodesManager, "updateFilesystem");
            $scope.available = [disk];

            $scope.availableConfirmFormatAndMount(disk);
            expect($scope.filesystems).toEqual([{
                "name": disk.name,
                "size_human": disk.size_human,
                "fstype": disk.fstype,
                "mount_point": disk.mount_point,
                "block_id": disk.block_id,
                "partition_id": disk.partition_id
            }]);
            expect($scope.available).toEqual([]);
        });
    });

    describe("isMountPointInvalid", function() {

        it("returns false if mount_point is undefined", function() {
            var controller = makeController();

            expect($scope.isMountPointInvalid()).toBe(false);
        });

        it("returns false if mount_point is empty", function() {
            var controller = makeController();

            expect($scope.isMountPointInvalid("")).toBe(false);
        });

        it("returns true if mount_point doesn't start with '/'", function() {
            var controller = makeController();

            expect($scope.isMountPointInvalid("a")).toBe(true);
        });

        it("returns false if mount_point start with '/'", function() {
            var controller = makeController();

            expect($scope.isMountPointInvalid("/")).toBe(false);
        });
    });

    describe("canDelete", function() {

        it("returns true if fstype is null", function() {
            var controller = makeController();
            var disk = { fstype: null };

            expect($scope.canDelete(disk)).toBe(true);
        });

        it("returns true if fstype is empty", function() {
            var controller = makeController();
            var disk = { fstype: "" };

            expect($scope.canDelete(disk)).toBe(true);
        });

        it("returns false if fstype is not empty", function() {
            var controller = makeController();
            var disk = { fstype: "ext4" };

            expect($scope.canDelete(disk)).toBe(false);
        });
    });

    describe("availableDelete", function() {

        it("sets availableMode to DELETE", function() {
            var controller = makeController();
            $scope.availableMode = "other";

            $scope.availableDelete();

            expect($scope.availableMode).toBe("delete");
        });
    });

    describe("availableQuickDelete", function() {

        it("selects disks and deselects others", function() {
            var controller = makeController();
            var available = [{ $selected: false }, { $selected: true }];
            $scope.available = available;
            spyOn($scope, "updateAvailableSelection");
            spyOn($scope, "availableUnformat");
            spyOn($scope, "availableDelete");

            $scope.availableQuickDelete(available[0]);

            expect(available[0].$selected).toBe(true);
            expect(available[1].$selected).toBe(false);
        });

        it("calls updateAvailableSelection with force true", function() {
            var controller = makeController();
            var available = [{ $selected: false }, { $selected: true }];
            spyOn($scope, "updateAvailableSelection");
            spyOn($scope, "availableUnformat");
            spyOn($scope, "availableDelete");

            $scope.availableQuickDelete(available[0]);

            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("calls availableUnformat when hasUnmountedFilesystem returns true",
            function() {
                var controller = makeController();
                var available = [{ $selected: false }, { $selected: true }];
                spyOn($scope, "updateAvailableSelection");
                spyOn($scope, "availableUnformat");
                spyOn($scope, "availableDelete");
                spyOn($scope, "hasUnmountedFilesystem").and.returnValue(true);

                $scope.availableQuickDelete(available[0]);

                expect($scope.availableUnformat).toHaveBeenCalledWith(
                    available[0]);
                expect($scope.availableDelete).not.toHaveBeenCalled();
            });

        it("calls availableDelete when hasUnmountedFilesystem returns true",
            function() {
                var controller = makeController();
                var available = [{ $selected: false }, { $selected: true }];
                spyOn($scope, "updateAvailableSelection");
                spyOn($scope, "availableUnformat");
                spyOn($scope, "availableDelete");
                spyOn($scope, "hasUnmountedFilesystem").and.returnValue(false);

                $scope.availableQuickDelete(available[0]);

                expect($scope.availableDelete).toHaveBeenCalledWith();
                expect($scope.availableUnformat).not.toHaveBeenCalled();
            });
    });

    describe("getRemoveTypeText", function() {

        it("returns 'physical disk' for physical", function() {
            var controller = makeController();
            expect($scope.getRemoveTypeText({
                type: "physical"
            })).toBe("physical disk");
        });

        it("returns 'partition' for partition", function() {
            var controller = makeController();
            expect($scope.getRemoveTypeText({
                type: "partition"
            })).toBe("partition");
        });

        it("returns 'volume group' for lvm-vg", function() {
            var controller = makeController();
            expect($scope.getRemoveTypeText({
                type: "lvm-vg"
            })).toBe("volume group");
        });

        it("returns 'logical volume' for virtual on lvm-vg", function() {
            var controller = makeController();
            expect($scope.getRemoveTypeText({
                type: "virtual",
                parent_type: "lvm-vg"
            })).toBe("logical volume");
        });

        it("returns parent_type + 'disk' for other virtual", function() {
            var controller = makeController();
            expect($scope.getRemoveTypeText({
                type: "virtual",
                parent_type: "raid0"
            })).toBe("raid0 disk");
        });
    });

    describe("availableConfirmDelete", function() {

        it("calls NodesManager.deleteVolumeGroup for lvm-vg", function() {
            var controller = makeController();
            var disk = {
                type: "lvm-vg",
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100)
            };
            $scope.available = [disk];
            spyOn(NodesManager, "deleteVolumeGroup");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmDelete(disk);
            expect(NodesManager.deleteVolumeGroup).toHaveBeenCalledWith(
                node, disk.block_id);
            expect($scope.available).toEqual([]);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("calls NodesManager.deletePartition for partition", function() {
            var controller = makeController();
            var disk = {
                type: "partition",
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100)
            };
            $scope.available = [disk];
            spyOn(NodesManager, "deletePartition");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmDelete(disk);
            expect(NodesManager.deletePartition).toHaveBeenCalledWith(
                node, disk.partition_id);
            expect($scope.available).toEqual([]);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });

        it("calls NodesManager.deleteDisk for disk", function() {
            var controller = makeController();
            var disk = {
                type: "physical",
                block_id: makeInteger(0, 100),
                partition_id: makeInteger(0, 100)
            };
            $scope.available = [disk];
            spyOn(NodesManager, "deleteDisk");
            spyOn($scope, "updateAvailableSelection");

            $scope.availableConfirmDelete(disk);
            expect(NodesManager.deleteDisk).toHaveBeenCalledWith(
                node, disk.block_id);
            expect($scope.available).toEqual([]);
            expect($scope.updateAvailableSelection).toHaveBeenCalledWith(
                true);
        });
    });

    describe("editTags", function() {

        it("doesnt sets editing to true if cannot edit", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(false);
            $scope.editing = false;
            $scope.editing_tags = false;
            $scope.editTags();
            expect($scope.editing).toBe(false);
            expect($scope.editing_tags).toBe(false);
        });

        it("sets editing to true", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(true);
            $scope.editing = false;
            $scope.editing_tags = false;
            $scope.editTags();
            expect($scope.editing).toBe(true);
            expect($scope.editing_tags).toBe(true);
        });
    });

    describe("cancelTags", function() {

        it("sets editing to false", function() {
            var controller = makeController();
            $scope.editing = true;
            $scope.editing_tags = true;
            $scope.cancelTags();
            expect($scope.editing).toBe(false);
            expect($scope.editing_tags).toBe(false);
        });

        it("calls updateDisks", function() {
            var controller = makeController();

            // Updates disks so we can check that updateStorage
            // is called.
            node.disks = [
                {
                    id: 0,
                    model: makeName("model"),
                    tags: [],
                    available_size: 0,
                    filesystem: null,
                    partitions: null
                }
            ];

            $scope.nodeLoaded();
            $rootScope.$digest();
            var filesystems = $scope.filesystems;
            var available = $scope.available;
            var used = $scope.used;
            $scope.editing = true;
            $scope.editing_tags = true;
            $scope.cancelTags();

            // Verify cancel calls updateStorage but doesn't change any data
            expect($scope.filesystems).toEqual(filesystems);
            expect($scope.available).toEqual(available);
            expect($scope.used).toEqual(used);
        });
    });

    describe("saveTags", function() {

        it("sets editing to false", function() {
            var controller = makeController();

            $scope.editing = true;
            $scope.editing_tags = true;
            $scope.saveTags();

            expect($scope.editing).toBe(false);
            expect($scope.editing_tags).toBe(false);
        });
    });
});
