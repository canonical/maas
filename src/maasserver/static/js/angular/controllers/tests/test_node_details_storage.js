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
            $scope: $scope
        });
        return controller;
    }

    it("sets initial values", function() {
        var controller = makeController();
        expect($scope.editing).toBe(false);
        expect($scope.column).toBe('model');
        expect($scope.has_disks).toBe(false);
        expect($scope.filesystems).toEqual([]);
        expect($scope.available).toEqual([]);
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
        var disks = [
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
        node.disks = disks;

        var filesystems = [
            {
                name: disks[2].name,
                size_human: disks[2].size_human,
                fstype: disks[2].filesystem.fstype,
                mount_point: disks[2].filesystem.mount_point,
                block_id: disks[2].id,
                partition_id: null
            },
            {
                name: disks[3].partitions[1].name,
                size_human: disks[3].partitions[1].size_human,
                fstype: disks[3].partitions[1].filesystem.fstype,
                mount_point: disks[3].partitions[1].filesystem.mount_point,
                block_id: disks[3].id,
                partition_id: disks[3].partitions[1].id
            }
        ];
        var available = [
            {
                name: disks[0].name,
                size_human: disks[0].size_human,
                type: disks[0].type,
                model: disks[0].model,
                serial: disks[0].serial,
                tags: disks[0].tags
            },
            {
                name: disks[1].name,
                size_human: disks[1].available_size_human,
                type: disks[1].type,
                model: disks[1].model,
                serial: disks[1].serial,
                tags: disks[1].tags
            },
            {
                name: disks[3].partitions[0].name,
                size_human: disks[3].size_human,
                type: disks[3].partitions[0].type,
                model: "",
                serial: "",
                tags: []
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

    describe("edit", function() {

        it("doesnt sets editing to true if cannot edit", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(false);
            $scope.editing = false;
            $scope.edit();
            expect($scope.editing).toBe(false);
        });

        it("sets editing to true", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(true);
            $scope.editing = false;
            $scope.edit();
            expect($scope.editing).toBe(true);
        });
    });

    describe("cancel", function() {

        it("sets editing to false", function() {
            var controller = makeController();
            $scope.editing = true;
            $scope.cancel();
            expect($scope.editing).toBe(false);
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
            $scope.cancel();

            // Verify cancel calls updateStorage but doesn't change any data
            expect($scope.filesystems).toEqual(filesystems);
            expect($scope.available).toEqual(available);
            expect($scope.used).toEqual(used);
        });
    });

    describe("save", function() {

        it("sets editing to false", function() {
            var controller = makeController();

            $scope.editing = true;
            $scope.save();

            expect($scope.editing).toBe(false);
        });

        it("calls updateNode with copy of node", function() {
            var controller = makeController();

            $scope.editing = true;
            $scope.save();

            var calledWithNode = updateNodeSpy.calls.argsFor(0)[0];
            expect(calledWithNode).not.toBe(node);
        });

        it("calls updateNode with new tags on disks", function() {
            var controller = makeController();
            var disks = [
                {
                    id: 0,
                    model: makeName("model"),
                    tags: [makeName("tag"), makeName("tag")]
                }
            ];
            var disksWithnewTags = angular.copy(disks);
            disksWithnewTags[0].tags = [makeName("tag"), makeName("tag")];

            node.disks = disks;
            $scope.editing = true;
            $scope.disks = disksWithnewTags;
            $scope.save();

            var calledWithNode = updateNodeSpy.calls.argsFor(0)[0];
            expect(calledWithNode.disks).toBe(disksWithnewTags);
            expect(calledWithNode.disks).not.toBe(
                disks);
        });
    });
});
