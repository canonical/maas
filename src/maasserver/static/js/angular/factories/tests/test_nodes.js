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

    // Copy node and remove $selected field.
    function stripSelected(node) {
        node = angular.copy(node);
        delete node.$selected;
        return node;
    }

    // Copy all nodes and remove the $selected field.
    function stripSelectedNodes(nodes) {
        nodes = angular.copy(nodes);
        angular.forEach(nodes, function(node) {
            delete node.$selected;
        });
        return nodes;
    }

    // Add $selected field to node with value.
    function addSelected(node, selected) {
        node.$selected = selected;
        return node;
    }

    // Add $selected field to all nodes with value.
    function addSelectedOnNodes(nodes, selected) {
        angular.forEach(nodes, function(node) {
            node.$selected = selected;
        });
        return nodes;
    }

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

    // Make a list of nodes.
    function makeNodes(count, selected) {
        var i, nodes = [];
        for(i = 0; i < count; i++) {
            nodes.push(makeNode(selected));
        }
        return nodes;
    }

    describe("getNodes", function() {

        it("returns nodes array", function() {
            var array = [ makeNode() ];
            NodesManager._nodes = array;
            expect(NodesManager.getNodes()).toBe(array);
        });
    });

    describe("loadNodes", function() {

        it("calls reloadNodes if the nodes are already loaded", function() {
            NodesManager._loaded = true;
            spyOn(NodesManager, "reloadNodes");
            NodesManager.loadNodes();
            expect(NodesManager.reloadNodes).toHaveBeenCalled();
        });

        it("calls node.list", function(done) {
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.loadNodes().then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.list");
                done();
            });
        });

        it("loads nodes list without replacing it", function(done) {
            var fakeNode = makeNode();
            var nodes = NodesManager.getNodes();
            webSocket.returnData.push(makeFakeResponse([fakeNode]));
            NodesManager.loadNodes().then(function(nodes) {
                expect(nodes).toEqual([addSelected(fakeNode, false)]);
                expect(nodes).toBe(nodes);
                done();
            });
        });

        it("batch calls in groups of 50", function(done) {
            var i, fakeNodes = [];
            for(i = 0; i < 3; i++) {
                var groupOfNodes = makeNodes(50);
                fakeNodes.push.apply(fakeNodes, groupOfNodes);
                webSocket.returnData.push(makeFakeResponse(groupOfNodes));
            }
            // A total of 4 calls should be completed, with the last one
            // being an empty list of nodes.
            webSocket.returnData.push(makeFakeResponse([]));
            NodesManager.loadNodes().then(function(nodes) {
                expect(nodes).toEqual(addSelectedOnNodes(fakeNodes, false));
                expect(webSocket.sentData.length).toBe(4);
                expect(webSocket.receivedData.length).toBe(4);
                expect(
                    angular.fromJson(
                        webSocket.receivedData[3]).result).toEqual([]);
                done();
            });
        });

        it("batch calls with the last system_id", function(done) {
            var fakeNodes = makeNodes(50);
            var system_id = fakeNodes[fakeNodes.length-1].system_id;
            webSocket.returnData.push(makeFakeResponse(fakeNodes));
            // A total of 2 calls should be completed, with the last one
            // being an empty list of nodes.
            webSocket.returnData.push(makeFakeResponse([]));
            NodesManager.loadNodes().then(function(nodes) {
                // Expect first message to not have a start.
                first_msg = angular.fromJson(webSocket.sentData[0]);
                expect(first_msg.params.start).toBeUndefined();

                // Expect the second message to have the last system_id.
                second_msg = angular.fromJson(webSocket.sentData[1]);
                expect(second_msg.params.start).toEqual(system_id);
                done();
            });
        });

        it("sets loaded true when complete", function(done) {
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.loadNodes().then(function() {
                expect(NodesManager._loaded).toBe(true);
                done();
            });
        });

        it("sets isLoading to true while loading", function(done) {
            NodesManager._isLoading = false;
            webSocket.returnData.push(makeFakeResponse("error", true));
            NodesManager.loadNodes().then(null, function() {
                expect(NodesManager._isLoading).toBe(true);
                done();
            });
        });

        it("sets isLoading to false after loading", function(done) {
            NodesManager._isLoading = true;
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.loadNodes().then(function() {
                expect(NodesManager._isLoading).toBe(false);
                done();
            });
        });

        it("calls processActions after loading", function(done) {
            spyOn(NodesManager, "processActions");
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.loadNodes().then(function() {
                expect(NodesManager.processActions).toHaveBeenCalled();
                done();
            });
        });

        it("calls defer error handler on error", function(done) {
            var errorMsg = "Unable to load the nodes.";
            webSocket.returnData.push(makeFakeResponse(errorMsg, true));
            NodesManager.loadNodes().then(null, function(error) {
                expect(error).toBe(errorMsg);
                done();
            });
        });

        it("doesn't set loaded to true on error", function(done) {
            var errorMsg = "Unable to load the nodes.";
            webSocket.returnData.push(makeFakeResponse(errorMsg, true));
            NodesManager.loadNodes().then(null, function() {
                expect(NodesManager._loaded).toBe(false);
                done();
            });
        });

        it("returns nodes list in defer", function(done) {
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.loadNodes().then(function(nodes) {
                expect(nodes).toBe(NodesManager.getNodes());
                done();
            });
        });

        it("updates the node statuses", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse([node]));
            NodesManager.loadNodes().then(function(nodes) {
                expect(NodesManager._metadata.statuses).toEqual([{
                    name: node.status,
                    count: 1
                }]);
                done();
            });
        });

        it("updates the node owners", function(done) {
            var node = makeNode();
            webSocket.returnData.push(makeFakeResponse([node]));
            NodesManager.loadNodes().then(function(nodes) {
                expect(NodesManager._metadata.owners).toEqual([{
                    name: node.owner,
                    count: 1
                }]);
                done();
            });
        });
    });

    describe("reloadNodes", function() {

        beforeEach(function() {
            NodesManager._loaded = true;
        });

        it("calls loadNodes if the nodes are not loaded", function() {
            NodesManager._loaded = false;
            spyOn(NodesManager, "loadNodes");
            NodesManager.reloadNodes();
            expect(NodesManager.loadNodes).toHaveBeenCalled();
        });

        it("sets isLoading to true while reloading", function(done) {
            NodesManager._isLoading = false;
            webSocket.returnData.push(makeFakeResponse("error", true));
            NodesManager.reloadNodes().then(null, function() {
                expect(NodesManager._isLoading).toBe(true);
                done();
            });
        });

        it("sets isLoading to false after reloading", function(done) {
            NodesManager._isLoading = true;
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.reloadNodes().then(function() {
                expect(NodesManager._isLoading).toBe(false);
                done();
            });
        });

        it("calls processActions after loading", function(done) {
            spyOn(NodesManager, "processActions");
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.reloadNodes().then(function() {
                expect(NodesManager.processActions).toHaveBeenCalled();
                done();
            });
        });

        it("calls defer error handler on error", function(done) {
            var errorMsg = "Unable to reload the nodes.";
            webSocket.returnData.push(makeFakeResponse(errorMsg, true));
            NodesManager.reloadNodes().then(null, function(error) {
                expect(error).toBe(errorMsg);
                done();
            });
        });

        it("returns nodes list in defer", function(done) {
            webSocket.returnData.push(makeFakeResponse([makeNode()]));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(nodes).toBe(NodesManager.getNodes());
                done();
            });
        });

        it("adds new nodes to nodes list", function(done) {
            var currentNodes = [makeNode(), makeNode()];
            var newNodes = [makeNode(), makeNode()];
            var allNodes = currentNodes.concat(newNodes);
            NodesManager._nodes = currentNodes;
            webSocket.returnData.push(makeFakeResponse(allNodes));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(nodes).toEqual(allNodes);
                done();
            });
        });

        it("removes missing nodes from nodes list", function(done) {
            var currentNodes = [makeNode(), makeNode(), makeNode()];
            var removedNodes = angular.copy(currentNodes);
            removedNodes.splice(1, 1);
            NodesManager._nodes = currentNodes;
            webSocket.returnData.push(makeFakeResponse(removedNodes));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(nodes).toEqual(removedNodes);
                done();
            });
        });

        it("removes missing nodes from selected nodes list", function(done) {
            var currentNodes = [makeNode(), makeNode(), makeNode()];
            var removedNodes = angular.copy(currentNodes);
            removedNodes.splice(1, 1);
            NodesManager._nodes = currentNodes;
            NodesManager._selectedNodes = [currentNodes[0], currentNodes[1]];
            webSocket.returnData.push(makeFakeResponse(removedNodes));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(NodesManager._selectedNodes).toEqual([currentNodes[0]]);
                done();
            });
        });

        it("updates nodes in nodes list", function(done) {
            var currentNodes = [makeNode(), makeNode()];
            var updatedNodes = angular.copy(currentNodes);
            updatedNodes[0].name = makeName("name");
            updatedNodes[1].name = makeName("name");
            NodesManager._nodes = currentNodes;
            webSocket.returnData.push(makeFakeResponse(updatedNodes));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(nodes).toEqual(updatedNodes);
                done();
            });
        });

        it("updates nodes in selected nodes list", function(done) {
            var currentNodes = [makeNode(true), makeNode(true)];
            var updatedNodes = stripSelectedNodes(currentNodes);
            updatedNodes[0].name = makeName("name");
            updatedNodes[1].name = makeName("name");
            NodesManager._nodes = currentNodes;
            NodesManager._selectedNodes = [currentNodes[0], currentNodes[1]];
            webSocket.returnData.push(makeFakeResponse(updatedNodes));
            NodesManager.reloadNodes().then(function(nodes) {
                expect(NodesManager._selectedNodes).toEqual(
                    addSelectedOnNodes(updatedNodes, true));
                done();
            });
        });
    });

    describe("enableAutoReload", function() {

        it("does nothing if already enabled", function() {
            spyOn(RegionConnection, "registerHandler");
            NodesManager._autoReload = true;
            NodesManager.enableAutoReload();
            expect(RegionConnection.registerHandler).not.toHaveBeenCalled();
        });

        it("adds handler and sets autoReload to true", function() {
            spyOn(RegionConnection, "registerHandler");
            NodesManager.enableAutoReload();
            expect(RegionConnection.registerHandler).toHaveBeenCalled();
            expect(NodesManager._autoReload).toBe(true);
        });
    });

    describe("disableAutoReload", function() {

        it("does nothing if already disabled", function() {
            spyOn(RegionConnection, "unregisterHandler");
            NodesManager._autoReload = false;
            NodesManager.disableAutoReload();
            expect(RegionConnection.unregisterHandler).not.toHaveBeenCalled();
        });

        it("removes handler and sets autoReload to false", function() {
            spyOn(RegionConnection, "unregisterHandler");
            NodesManager._autoReload = true;
            NodesManager.disableAutoReload();
            expect(RegionConnection.unregisterHandler).toHaveBeenCalled();
            expect(NodesManager._autoReload).toBe(false);
        });
    });

    describe("getNode", function() {

        it("calls node.get", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(fakeNode));
            NodesManager.getNode(fakeNode.system_id).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.get");
                done();
            });
        });

        it("calls node.get with node system_id", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(fakeNode));
            NodesManager.getNode(fakeNode.system_id).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                done();
            });
        });

        it("updates node in nodes and selectedNodes list", function(done) {
            var fakeNode = makeNode();
            var updatedNode = angular.copy(fakeNode);
            updatedNode.name = makeName("name");

            NodesManager._nodes.push(fakeNode);
            NodesManager._selectedNodes.push(fakeNode);
            webSocket.returnData.push(makeFakeResponse(updatedNode));
            NodesManager.getNode(fakeNode.system_id).then(function() {
                expect(NodesManager._nodes[0].name).toBe(updatedNode.name);
                expect(NodesManager._selectedNodes[0].name).toBe(
                    updatedNode.name);
                done();
            });
        });

        it("calls defer error handler on error", function(done) {
            var errorMsg = "No node with the given system_id.";
            webSocket.returnData.push(makeFakeResponse(errorMsg, true));
            NodesManager.getNode(makeName("system_id")).then(
                null, function(error) {
                    expect(error).toBe(errorMsg);
                    done();
                });
        });
    });

    describe("updateNode", function() {

        it("calls node.update", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(fakeNode));
            NodesManager.updateNode(fakeNode).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.update");
                done();
            });
        });

        it("calls node.update with node", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(fakeNode));
            NodesManager.updateNode(fakeNode).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.params).toEqual(fakeNode);
                done();
            });
        });

        it("updates node in nodes and selectedNodes list", function(done) {
            var fakeNode = makeNode();
            var updatedNode = angular.copy(fakeNode);
            updatedNode.name = makeName("name");

            NodesManager._nodes.push(fakeNode);
            NodesManager._selectedNodes.push(fakeNode);
            webSocket.returnData.push(makeFakeResponse(updatedNode));
            NodesManager.updateNode(updatedNode).then(function() {
                expect(NodesManager._nodes[0].name).toBe(updatedNode.name);
                expect(NodesManager._selectedNodes[0].name).toBe(
                    updatedNode.name);
                done();
            });
        });

        it("calls defer error handler on error", function(done) {
            var errorMsg = "Unable to update node";
            webSocket.returnData.push(makeFakeResponse(errorMsg, true));
            NodesManager.updateNode(makeNode()).then(null, function(error) {
                expect(error).toBe(errorMsg);
                done();
            });
        });
    });

    describe("deleteNode", function() {

        it("calls node.delete", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.deleteNode(fakeNode).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.method).toBe("node.delete");
                done();
            });
        });

        it("calls node.delete with node system_id", function(done) {
            var fakeNode = makeNode();
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.deleteNode(fakeNode).then(function() {
                var sentObject = angular.fromJson(webSocket.sentData[0]);
                expect(sentObject.params.system_id).toBe(fakeNode.system_id);
                done();
            });
        });

        it("deletes node in nodes and selectedNodes list", function(done) {
            var fakeNode = makeNode();
            NodesManager._nodes.push(fakeNode);
            NodesManager._selectedNodes.push(fakeNode);
            webSocket.returnData.push(makeFakeResponse(null));
            NodesManager.deleteNode(fakeNode).then(function() {
                expect(NodesManager._nodes.length).toBe(0);
                expect(NodesManager._selectedNodes.length).toBe(0);
                done();
            });
        });
    });

    describe("onNotify", function() {

        it("adds notify to queue", function() {
            var node = makeNode();
            NodesManager._isLoading = true;
            NodesManager.onNotify("create", node);
            expect(NodesManager._actionQueue).toEqual([{
                action: "create",
                data: node
            }]);
        });

        it("skips processActions when isLoading is true",
            function() {
                spyOn(NodesManager, "processActions");
                NodesManager._isLoading = true;
                NodesManager.onNotify("create", makeName("system_id"));
                expect(NodesManager.processActions).not.toHaveBeenCalled();
            });

        it("calls processActions when isLoading is false",
            function() {
                spyOn(NodesManager, "processActions");
                NodesManager._isLoading = false;
                NodesManager.onNotify("create", makeName("system_id"));
                expect(NodesManager.processActions).toHaveBeenCalled();
            });
    });

    describe("processActions", function() {

        it("adds node to nodes list on create action", function() {
            var fakeNode = makeNode();
            NodesManager._actionQueue.push({
                action: "create",
                data: fakeNode
            });
            NodesManager.processActions();
            expect(NodesManager._nodes).toEqual(
                [addSelected(fakeNode, false)]);
        });

        it("updates node in nodes list on update action", function() {
            var fakeNode = makeNode(false);
            var updatedNode = stripSelected(fakeNode);
            updatedNode.name = makeName("name");
            NodesManager._nodes.push(fakeNode);
            NodesManager._actionQueue.push({
                action: "update",
                data: updatedNode
            });
            NodesManager.processActions();
            expect(NodesManager._nodes).toEqual(
                [addSelected(updatedNode, false)]);
        });

        it("updates node in selected nodes on update action", function() {
            var fakeNode = makeNode(true);
            var updatedNode = stripSelected(fakeNode);
            updatedNode.name = makeName("name");
            NodesManager._nodes.push(fakeNode);
            NodesManager._selectedNodes.push(fakeNode);
            NodesManager._actionQueue.push({
                action: "update",
                data: updatedNode
            });
            NodesManager.processActions();
            expect(NodesManager._selectedNodes).toEqual(
                [addSelected(updatedNode, true)]);
        });

        it("deletes node in nodes list on delete action", function() {
            var fakeNode = makeNode();
            NodesManager._nodes.push(fakeNode);
            NodesManager._actionQueue.push({
                action: "delete",
                data: fakeNode.system_id
            });
            NodesManager.processActions();
            expect(NodesManager._nodes.length).toBe(0);
        });

        it("deletes node in selected nodes on delete action", function() {
            var fakeNode = makeNode();
            NodesManager._nodes.push(fakeNode);
            NodesManager._selectedNodes.push(fakeNode);
            NodesManager._actionQueue.push({
                action: "delete",
                data: fakeNode.system_id
            });
            NodesManager.processActions();
            expect(NodesManager._selectedNodes.length).toBe(0);
        });

        it("processes multiple actions in one call", function() {
            NodesManager._actionQueue = [
                {
                    action: "delete",
                    data: makeName("system_id")
                },
                {
                    action: "delete",
                    data: makeName("system_id")
                }
            ];
            NodesManager.processActions();
            expect(NodesManager._actionQueue.length).toBe(0);
        });
    });

    describe("getActiveNode", function() {

        it("returns active node", function() {
            var node = makeNode();
            NodesManager._activeNode = node;
            expect(NodesManager.getActiveNode()).toBe(node);
        });
    });

    describe("setActiveNode", function() {

        it("calls node.get and updates activeNode", function(done) {
            var otherNode = makeNode();
            var node = makeNode();
            NodesManager._activeNode = otherNode;
            webSocket.returnData.push(makeFakeResponse(node));
            NodesManager.setActiveNode(node).then(function(node) {
                expect(
                    angular.fromJson(
                        webSocket.sentData[0]).method).toBe("node.get");
                expect(NodesManager._activeNode).toEqual(node);
                done();
            });
        });

        it("clears activeNode", function(done) {
            var otherNode = makeNode();
            var node = makeNode();
            NodesManager._activeNode = otherNode;
            webSocket.returnData.push(makeFakeResponse("error", true));
            NodesManager.setActiveNode(node).then(null, function(node) {
                expect(NodesManager._activeNode).toBeNull();
                done();
            });
        });
    });

    describe("getSelectedNodes", function() {

        it("returns selected nodes", function() {
            var nodes = [makeNode()];
            NodesManager._selectedNodes = nodes;
            expect(NodesManager.getSelectedNodes()).toBe(nodes);
        });
    });

    describe("selectNode", function() {

        it("adds node to selected nodes", function() {
            var node = makeNode(false);
            NodesManager._nodes.push(node);
            NodesManager.selectNode(node.system_id);
            expect(NodesManager._selectedNodes).toEqual(
                [addSelected(node, true)]);
        });

        it("doesnt add the same node twice", function() {
            var node = makeNode(false);
            NodesManager._nodes.push(node);
            NodesManager.selectNode(node.system_id);
            NodesManager.selectNode(node.system_id);
            expect(NodesManager._selectedNodes).toEqual(
                [addSelected(node, true)]);
        });
    });

    describe("unselectNode", function() {

        var node;
        beforeEach(function() {
            node = makeNode(false);
            NodesManager._nodes.push(node);
            NodesManager.selectNode(node.system_id);
        });

        it("removes node from selected nodes", function() {
            NodesManager.unselectNode(node.system_id);
            expect(NodesManager._selectedNodes).toEqual([]);
            expect(node.$selected).toBe(false);
        });

        it("doesnt error on unselect twice", function() {
            NodesManager.unselectNode(node.system_id);
            NodesManager.unselectNode(node.system_id);
            expect(NodesManager._selectedNodes).toEqual([]);
            expect(node.$selected).toBe(false);
        });
    });

    describe("isSelected", function() {

        var node;
        beforeEach(function() {
            node = makeNode(false);
            NodesManager._nodes.push(node);
        });

        it("returns true when selected", function() {
            NodesManager.selectNode(node.system_id);
            expect(NodesManager.isSelected(node.system_id)).toBe(true);
        });

        it("returns false when not selected", function() {
            NodesManager.selectNode(node.system_id);
            NodesManager.unselectNode(node.system_id);
            expect(NodesManager.isSelected(node.system_id)).toBe(false);
        });
    });

    var scenarios = [
        {
            field: 'status',
            metadata: 'statuses'
        },
        {
            field: 'owner',
            metadata: 'owners'
        }
    ];

    angular.forEach(scenarios, function(scenario) {

        describe("_updateMetadata:" + scenario.field, function() {

            it("adds value if missing", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: node[scenario.field],
                    count: 1
                }]);
            });

            it("increments count for value", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: node[scenario.field],
                    count: 1
                }]);
                NodesManager._updateMetadata(node, "create");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: node[scenario.field],
                    count: 2
                }]);
                NodesManager._updateMetadata(node, "create");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: node[scenario.field],
                    count: 3
                }]);
            });

            it("decrements count for value", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                NodesManager._updateMetadata(node, "create");
                NodesManager._updateMetadata(node, "delete");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: node[scenario.field],
                    count: 1
                }]);
            });

            it("removes value when count is 0", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                NodesManager._updateMetadata(node, "delete");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([]);
            });

            it("update doesn't add value if missing", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "update");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([]);
            });

            it("update decrements value then increments new value", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                NodesManager._updateMetadata(node, "create");
                NodesManager._nodes.push(node);
                var updatedNode = angular.copy(node);
                updatedNode[scenario.field] = makeName(scenario.field);
                NodesManager._updateMetadata(updatedNode, "update");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([
                    {
                        name: node[scenario.field],
                        count: 1
                    },
                    {
                        name: updatedNode[scenario.field],
                        count: 1
                    }]);
            });

            it("update removes old value then adds new value", function() {
                var node = makeNode();
                NodesManager._updateMetadata(node, "create");
                NodesManager._nodes.push(node);
                var updatedNode = angular.copy(node);
                updatedNode[scenario.field] = makeName(scenario.field);
                NodesManager._updateMetadata(updatedNode, "update");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: updatedNode[scenario.field],
                    count: 1
                }]);
            });

            it("ignores empty values", function() {
                var node = makeNode();
                node.owner = "";
                node.status = "";
                NodesManager._updateMetadata(node, "create");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([]);
            });

            it("update handlers empty old values", function() {
                var node = makeNode();
                node[scenario.field] = "";
                NodesManager._updateMetadata(node, "create");
                NodesManager._nodes.push(node);
                var updatedNode = angular.copy(node);
                updatedNode[scenario.field] = makeName(scenario.field);
                NodesManager._updateMetadata(updatedNode, "update");
                expect(NodesManager._metadata[scenario.metadata]).toEqual([{
                    name: updatedNode[scenario.field],
                    count: 1
                }]);
            });
        });

    });
});
