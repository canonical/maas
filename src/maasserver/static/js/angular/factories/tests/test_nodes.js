/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodesManager.
 */


describe("NodesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the NodesManager and RegionConnection factory.
    var NodesManager, RegionConnection, webSocket;
    beforeEach(inject(function($injector) {
        NodesManager = $injector.get("NodesManager");
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
    function makeNode(selected) {
        var node = {
            system_id: makeName("system_id"),
            name: makeName("name"),
            status: makeName("status"),
            owner: makeName("owner")
        };
        if(angular.isDefined(selected)) {
            node.$selected = selected;
        }
        return node;
    }

    it("set requires attributes", function() {
        expect(NodesManager._pk).toBe("system_id");
        expect(NodesManager._handler).toBe("node");
        expect(Object.keys(NodesManager._metadataAttributes)).toEqual(
            ["status", "owner", "tags", "zone", "subnets", "fabrics",
            "spaces", "storage_tags"]);
    });

    describe("create", function() {

        it("calls node.create with node", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse(node));
            NodesManager.create(node).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create");
                expect(sentObject.params).toEqual(node);
                done();
            });
        });
    });

    describe("performAction", function() {

        it("calls node.action with system_id and action", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse("deleted"));
            NodesManager.performAction(node, "delete").then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.action");
                expect(sentObject.params.system_id).toBe(node.system_id);
                expect(sentObject.params.action).toBe("delete");
                expect(sentObject.params.extra).toEqual({});
                done();
            });
        });

        it("calls node.action with extra", function(done) {
            var node = makeNode();
            var extra = {
                osystem: makeName("os")
            };
            webSocket.returnData.push(makeFakeResponse("deployed"));
            NodesManager.performAction(node, "deploy", extra).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.action");
                expect(sentObject.params.system_id).toBe(node.system_id);
                expect(sentObject.params.action).toBe("deploy");
                expect(sentObject.params.extra).toEqual(extra);
                done();
            });
        });
    });

    describe("checkPowerState", function() {

        it("calls node.check_power with system_id", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse("on"));
            NodesManager.checkPowerState(node).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.check_power");
                expect(sentObject.params.system_id).toBe(node.system_id);
                done();
            });
        });

        it("sets power_state to results", function(done) {
            var node = makeNode();
            var power_state = makeName("state");
            webSocket.returnData.push(makeFakeResponse(power_state));
            NodesManager.checkPowerState(node).then(function(state) {
                expect(node.power_state).toBe(power_state);
                expect(state).toBe(power_state);
                done();
            });
        });

        it("sets power_state to error on error and logs error",
            function(done) {
                var node = makeNode();
                var error = makeName("error");
                spyOn(console, "log");
                webSocket.returnData.push(makeFakeResponse(error, true));
                NodesManager.checkPowerState(node).then(function(state) {
                    expect(node.power_state).toBe("error");
                    expect(state).toBe("error");
                    expect(console.log).toHaveBeenCalledWith(error);
                    done();
                });
            });
    });

    describe("createPhysicalInterface", function() {

        it("calls node.create_physical with system_id without params",
            function(done) {
                var node = makeNode();
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createPhysicalInterface(node).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_physical");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        done();
                    });
            });

        it("calls node.create_physical with params",
            function(done) {
                var node = makeNode();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createPhysicalInterface(node, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_physical");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.vlan).toBe(params.vlan);
                        done();
                    });
            });
    });

    describe("createVLANInterface", function() {

        it("calls node.create_vlan with system_id without params",
            function(done) {
                var node = makeNode();
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createVLANInterface(node).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_vlan");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        done();
                    });
            });

        it("calls node.create_vlan with params",
            function(done) {
                var node = makeNode();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createVLANInterface(node, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_vlan");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.vlan).toBe(params.vlan);
                        done();
                    });
            });
    });

    describe("createBondInterface", function() {

        it("calls node.create_bond with system_id without params",
            function(done) {
                var node = makeNode();
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createBondInterface(node).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_bond");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        done();
                    });
            });

        it("calls node.create_bond with params",
            function(done) {
                var node = makeNode();
                var params = {
                    vlan: makeInteger(0, 100)
                };
                webSocket.returnData.push(makeFakeResponse("created"));
                NodesManager.createBondInterface(node, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_bond");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.vlan).toBe(params.vlan);
                        done();
                    });
            });
    });

    describe("updateInterface", function() {

        it("calls node.update_interface with system_id and interface_id",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.updateInterface(node, interface_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.update_interface");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        done();
                    });
            });

        it("calls node.update_interface with params",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                var params = {
                    name: makeName("eth0")
                };
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.updateInterface(node, interface_id, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.update_interface");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        expect(sentObject.params.name).toBe(params.name);
                        done();
                    });
            });
    });

    describe("deleteInterface", function() {

        it("calls node.delete_interface with correct params",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.deleteInterface(node, interface_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.delete_interface");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        done();
                    });
            });
    });

    describe("linkSubnet", function() {

        it("calls node.link_subnet with system_id and interface_id",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.linkSubnet(node, interface_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.link_subnet");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        done();
                    });
            });

        it("calls node.link_subnet with params",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                var params = {
                    name: makeName("eth0")
                };
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.linkSubnet(node, interface_id, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.link_subnet");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        expect(sentObject.params.name).toBe(params.name);
                        done();
                    });
            });
    });

    describe("unlinkSubnet", function() {

        it("calls node.unlink_subnet with correct params",
            function(done) {
                var node = makeNode(), interface_id = makeInteger(0, 100);
                var link_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("updated"));
                NodesManager.unlinkSubnet(node, interface_id, link_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.unlink_subnet");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.interface_id).toBe(
                            interface_id);
                        expect(sentObject.params.link_id).toBe(
                            link_id);
                        done();
                    });
            });
    });

    describe("updateFilesystem", function() {
        it("calls node.update_filesystem", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.updateFilesystem(
                    fakeNode.system_id, makeName("block_id"),
                    makeName("partition_id"), makeName("fstype"),
                    makeName("mount_point")).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.update_filesystem");
                done();
            });
        });

        it("calls node.update_filesystem with params", function(done) {
            var fakeNode = makeNode();
            var block_id = makeName("block_id");
            var partition_id = makeName("partition_id");
            var fstype = makeName("fstype");
            var mount_point = makeName("mount_point");
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.updateFilesystem(
                    fakeNode, block_id, partition_id,
                    fstype, mount_point).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.update_filesystem");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(block_id);
                expect(sentObject.params.partition_id).toBe(partition_id);
                expect(sentObject.params.fstype).toBe(fstype);
                expect(sentObject.params.mount_point).toBe(mount_point);
                done();
            });
        });
    });

    describe("updateDiskTags", function() {

        it("calls node.update_disk_tags", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.updateDiskTags(
                    fakeNode, makeName("block_id"),
                    [ makeName("tag") ]).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.update_disk_tags");
                done();
            });
        });

        it("calls node.update_disk_tags with params", function(done) {
            var fakeNode = makeNode();
            var block_id = makeName("block_id");
            var tags = [ makeName("tag") ];
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.updateDiskTags(
                    fakeNode, block_id, tags).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.update_disk_tags");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(block_id);
                expect(sentObject.params.tags[0]).toBe(tags[0]);
                done();
            });
        });
    });

    describe("deleteDisk", function() {

        it("calls node.delete_disk with correct params",
            function(done) {
                var node = makeNode(), block_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.deleteDisk(node, block_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.delete_disk");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.block_id).toBe(
                            block_id);
                        done();
                    });
            });
    });

    describe("deletePartition", function() {

        it("calls node.delete_partition with correct params",
            function(done) {
                var node = makeNode(), partition_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.deletePartition(node, partition_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.delete_partition");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.partition_id).toBe(
                            partition_id);
                        done();
                    });
            });
    });

    describe("deleteVolumeGroup", function() {

        it("calls node.delete_volume_group with correct params",
            function(done) {
                var node = makeNode(), volume_group_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.deleteVolumeGroup(node, volume_group_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.delete_volume_group");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.volume_group_id).toBe(
                            volume_group_id);
                        done();
                    });
            });
    });

    describe("deleteCacheSet", function() {

        it("calls node.delete_cache_set with correct params",
            function(done) {
                var node = makeNode(), cache_set_id = makeInteger(0, 100);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.deleteCacheSet(node, cache_set_id).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.delete_cache_set");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.cache_set_id).toBe(
                            cache_set_id);
                        done();
                    });
            });
    });

    describe("createPartition", function() {

        it("calls node.create_partition with correct params",
            function(done) {
                var node = makeNode(), block_id = makeInteger(0, 100);
                var size = makeInteger(1024 * 1024, 1024 * 1024 * 1024);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.createPartition(node, block_id, size).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_partition");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.block_id).toBe(
                            block_id);
                        expect(sentObject.params.partition_size).toBe(
                            size);
                        done();
                    });
            });

        it("calls node.create_partition with extra params",
            function(done) {
                var params = { fstype: "ext4" };
                var node = makeNode(), block_id = makeInteger(0, 100);
                var size = makeInteger(1024 * 1024, 1024 * 1024 * 1024);
                webSocket.returnData.push(makeFakeResponse("deleted"));
                NodesManager.createPartition(node, block_id, size, params).then(
                    function() {
                        var sentObject = angular.fromJson(
                            webSocket.sentData[0]);
                        expect(sentObject.method).toBe(
                            "node.create_partition");
                        expect(sentObject.params.system_id).toBe(
                            node.system_id);
                        expect(sentObject.params.block_id).toBe(
                            block_id);
                        expect(sentObject.params.partition_size).toBe(
                            size);
                        expect(sentObject.params.fstype).toBe("ext4");
                        done();
                    });
            });
    });

    describe("createCacheSet", function() {

        it("calls node.create_cache_set", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createCacheSet(
                    fakeNode, "", "").then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_cache_set");
                done();
            });
        });

        it("calls node.create_cache_set with params", function(done) {
            var fakeNode = makeNode();
            var block_id = makeName("block_id");
            var partition_id = makeName("block_id");
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createCacheSet(
                    fakeNode, block_id, partition_id).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_cache_set");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(block_id);
                expect(sentObject.params.partition_id).toBe(partition_id);
                done();
            });
        });
    });

    describe("createBcache", function() {

        it("calls node.create_bcache", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createBcache(
                    fakeNode, {}).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_bcache");
                done();
            });
        });

        it("calls node.create_bcache with params", function(done) {
            var fakeNode = makeNode();
            var params = {
                block_id: makeName("block_id"),
                partition_id: makeName("block_id")
            };
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createBcache(
                    fakeNode, params).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_bcache");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(params.block_id);
                expect(sentObject.params.partition_id).toBe(
                    params.partition_id);
                done();
            });
        });
    });

    describe("createRAID", function() {

        it("calls node.create_raid", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createRAID(
                    fakeNode, {}).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_raid");
                done();
            });
        });

        it("calls node.create_raid with params", function(done) {
            var fakeNode = makeNode();
            var params = {
                block_id: makeName("block_id"),
                partition_id: makeName("block_id")
            };
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createRAID(
                    fakeNode, params).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_raid");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(params.block_id);
                expect(sentObject.params.partition_id).toBe(
                    params.partition_id);
                done();
            });
        });
    });

    describe("createVolumeGroup", function() {

        it("calls node.create_volume_group", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createVolumeGroup(
                    fakeNode, {}).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_volume_group");
                done();
            });
        });

        it("calls node.create_volume_group with params", function(done) {
            var fakeNode = makeNode();
            var params = {
                block_id: makeName("block_id"),
                partition_id: makeName("block_id")
            };
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createVolumeGroup(
                    fakeNode, params).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_volume_group");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(params.block_id);
                expect(sentObject.params.partition_id).toBe(
                    params.partition_id);
                done();
            });
        });
    });

    describe("createLogicalVolume", function() {

        it("calls node.create_logical_volume", function(done) {
            var fakeNode = makeNode();
            var volume_group_id = makeInteger(0, 100);
            var name = makeName("lv");
            var size = makeInteger(1000 * 1000, 1000 * 1000 * 1000);
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createLogicalVolume(
                    fakeNode, volume_group_id, name, size).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_logical_volume");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.volume_group_id).toBe(
                    volume_group_id);
                expect(sentObject.params.name).toBe(name);
                expect(sentObject.params.size).toBe(size);
                done();
            });
        });

        it("calls node.create_logical_volume with extra", function(done) {
            var fakeNode = makeNode();
            var volume_group_id = makeInteger(0, 100);
            var name = makeName("lv");
            var size = makeInteger(1000 * 1000, 1000 * 1000 * 1000);
            var extra = { fstype: "ext4" };
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.createLogicalVolume(
                    fakeNode, volume_group_id, name, size, extra).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.create_logical_volume");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.volume_group_id).toBe(
                    volume_group_id);
                expect(sentObject.params.name).toBe(name);
                expect(sentObject.params.size).toBe(size);
                expect(sentObject.params.fstype).toBe("ext4");
                done();
            });
        });
    });

    describe("setBootDisk", function() {

        it("calls node.set_boot_disk", function(done) {
            var fakeNode = makeNode();
            var block_id = makeInteger(0, 100);
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.setBootDisk(
                    fakeNode, block_id).then(
                        function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.set_boot_disk");
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                expect(sentObject.params.block_id).toBe(
                    block_id);
                done();
            });
        });
    });
});
