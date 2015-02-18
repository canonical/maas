/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes Manager
 *
 * Manages all of the nodes in the browser. This manager is used for the
 * node listing and the node view page. The manager uses the RegionConnection
 * to load the nodes, update the nodes, and listen for notification events
 * about nodes.
 */

angular.module('MAAS').factory(
    'NodesManager',
    ['$q', '$rootScope', 'RegionConnection', function(
            $q, $rootScope, RegionConnection) {

        // Actions that are used to update the statuses metadata.
        var METADATA_ACTIONS = {
            CREATE: "create",
            UPDATE: "update",
            DELETE: "delete"
        };

        // Returns index of node by system_id in array.
        function getIndexOfNode(nodes, system_id) {
            var i;
            for(i = 0, len = nodes.length; i < len; i++) {
                if(nodes[i].system_id === system_id) {
                    return i;
                }
            }
            return -1;
        }

        // Replaces the node in the array at the same index.
        function replaceNodeInArray(nodes, node) {
            var idx = getIndexOfNode(nodes, node.system_id);
            if(idx >= 0) {
                // Keep the current selection on the node.
                node.$selected = nodes[idx].$selected;
                nodes[idx] = node;
            }
        }

        // Remove the node from the array.
        function removeNodeByIdFromArray(nodes, system_id) {
            var idx = getIndexOfNode(nodes, system_id);
            if(idx >= 0) {
                nodes.splice(idx, 1);
            }
        }

        // Loads the nodes in batches of 50 into the given nodesArray. If
        // extra_func is given it will pass each loaded node to that function.
        function batchLoadNodes(nodesArray, extra_func) {
            var defer = $q.defer();
            function callLoad() {
                var params = {
                    count: 50
                };
                // Get the last system_id in the list so the region knows to
                // start at that offset.
                if(nodesArray.length > 0) {
                    params.start = nodesArray[nodesArray.length-1].system_id;
                }
                RegionConnection.callMethod(
                    "node.list", params).then(function(nodes) {
                        // Pass each node to extra_func if given.
                        if(angular.isFunction(extra_func)) {
                            angular.forEach(nodes, function(node) {
                                extra_func(node);
                            });
                        }

                        nodesArray.push.apply(nodesArray, nodes);
                        if(nodes.length === 50) {
                            // Could be more nodes, request the next 50.
                            callLoad(nodesArray);
                        } else {
                            defer.resolve(nodesArray);
                        }
                    }, defer.reject);
            }
            callLoad();
            return defer.promise;
        }

        // Return the metadata object from `metadatas` matching `name`.
        function getMetadata(metadatas, name) {
            var i;
            for(i = 0; i < metadatas.length; i++) {
                if(metadatas[i].name === name) {
                    return metadatas[i];
                }
            }
            return null;
        }

        // Update the metadata in `metadatas` for the node with field and
        // based on the action.
        function updateMetadata(metadatas, node, field, action, oldNode) {
            var value = node[field];
            // Ignore blank values as it looks ugly in the list and we don't
            // want it to show.
            if(value === '') {
                return;
            }

            var metadata = getMetadata(metadatas, value);
            if(action === METADATA_ACTIONS.CREATE) {
                if(!metadata) {
                    metadata = {
                        name: value,
                        count: 1
                    };
                    metadatas.push(metadata);
                } else {
                    metadata.count += 1;
                }
            } else if(action === METADATA_ACTIONS.DELETE && metadata) {
                metadata.count -= 1;
                if(metadata.count <= 0) {
                    metadatas.splice(metadatas.indexOf(metadata), 1);
                }
            } else if(action === METADATA_ACTIONS.UPDATE) {
                if(angular.isDefined(oldNode) && oldNode[field] !== value) {
                    if(oldNode[field] !== "") {
                        // Decrement the old value
                        var oldValue = getMetadata(metadatas, oldNode[field]);
                        oldValue.count -= 1;
                        if(oldValue.count <= 0) {
                            metadatas.splice(
                                metadatas.indexOf(oldValue), 1);
                        }
                    }

                    // Increment the new value with the "create"
                    // operation.
                    updateMetadata(
                        metadatas, node, field,
                        METADATA_ACTIONS.CREATE, oldNode);
                }
            }
        }

        // Constructor
        function NodesManager() {
            // Holds the node that has all details synced. This is the node
            // that is being displayed on the node details view.
            this._activeNode = null;

            // Holds all nodes in the system. This list must always be the same
            // object, and the nodes in the list only have enough information
            // for showing in the listing. For full information you need to
            // make the node active.
            this._nodes = [];

            // True when all of the nodes have been loaded. This is done on
            // intial connection to the region.
            this._loaded = false;

            // True when the nodes list is currently being loaded or reloaded.
            // Actions will not be processed while this is false.
            this._isLoading = false;

            // Holds all of the notify actions that need to be processed. This
            // is used to hold the actions while the nodes are being loaded.
            // Once all of the nodes are loaded the queue will be processed.
            this._actionQueue = [];

            // Holds list of all of the currently selected nodes. This is held
            // in a seperate list to remove the need to loop through the full
            // listing to grab the selected nodes.
            this._selectedNodes = [];

            // Set to true when the nodes list should reload upon re-connection
            // to the region.
            this._autoReload = false;

            // Holds metadata information that is used to add filters to the
            // search bar.
            this._metadata = {
                statuses: [],
                owners:[]
            };

            // Listen for notify events for the node object.
            var self = this;
            RegionConnection.registerNotifier("node", function(action, data) {
                self.onNotify(action, data);
            });
        }

        // Return list of nodes.
        NodesManager.prototype.getNodes = function() {
            return this._nodes;
        };

        // Load all the nodes.
        NodesManager.prototype.loadNodes = function() {
            // If the nodes have already been loaded then, we need to
            // update the nodes list not load the initial list.
            if(this._loaded) {
                return this.reloadNodes();
            }

            var self = this;
            this._isLoading = true;
            return batchLoadNodes(this._nodes, function(node) {
                node.$selected = false;
                self._updateMetadata(node, METADATA_ACTIONS.CREATE);
            }).then(function() {
                self._loaded = true;
                self._isLoading = false;
                self.processActions();
                return self._nodes;
            });
        };

        // Reload the nodes list.
        NodesManager.prototype.reloadNodes = function() {
            // If the nodes have not been loaded then, we need to
            // load the initial list.
            if(!this._loaded) {
                return this.loadNodes();
            }

            // Updates the nodes list with the reloaded nodes.
            var self = this;
            function updateNodes(nodes) {
                // Iterate in reverse so we can remove nodes inline, without
                // having to adjust the index.
                var i = self._nodes.length;
                while(i--) {
                    var node = self._nodes[i];
                    var updatedIdx = getIndexOfNode(
                        nodes, node.system_id);
                    if(updatedIdx === -1) {
                        self._updateMetadata(node, METADATA_ACTIONS.DELETE);
                        self._nodes.splice(i, 1);
                        removeNodeByIdFromArray(
                            self._selectedNodes, node.system_id);
                    } else {
                        self._updateMetadata(
                            nodes[updatedIdx], METADATA_ACTIONS.UPDATE);
                        self._nodes[i] = nodes[updatedIdx];
                        nodes.splice(updatedIdx, 1);
                        replaceNodeInArray(self._selectedNodes, self._nodes[i]);
                    }
                }

                // The remain nodes in nodes are the new nodes.
                self._nodes.push.apply(self._nodes, nodes);
            }

            // The reload action loads all of the nodes into this list
            // instead of the nodes list. This list will then be used to
            // update the nodes list.
            var currentNodes = [];

            // Start the reload process and once complete call updateNodes.
            self._isLoading = true;
            return batchLoadNodes(currentNodes).then(function(nodes) {
                updateNodes(nodes);
                self._isLoading = false;
                self.processActions();
                return self._nodes;
            });
        };

        // Enables auto reloading of the node list on connection to region.
        NodesManager.prototype.enableAutoReload = function() {
            if(!this._autoReload) {
                this._autoReload = true;
                var self = this;
                this._reloadFunc = function() {
                    self.reloadNodes();
                };
                RegionConnection.registerHandler("open", this._reloadFunc);
            }
        };

        // Disable auto reloading of the node list on connection to region.
        NodesManager.prototype.disableAutoReload = function() {
            if(this._autoReload) {
                RegionConnection.unregisterHandler("open", this._reloadFunc);
                this._reloadFunc = null;
                this._autoReload = false;
            }
        };

        // True when the initial node list has finished loading.
        NodesManager.prototype.isLoaded = function() {
            return this._loaded;
        };

        // True when the node list is currently being loaded or reloaded.
        NodesManager.prototype.isLoading = function() {
            return this._isLoading;
        };

        // Replace node in the nodes and selectedNodes list.
        NodesManager.prototype._replaceNode = function(node) {
            this._updateMetadata(node, METADATA_ACTIONS.UPDATE);
            replaceNodeInArray(this._nodes, node);
            replaceNodeInArray(this._selectedNodes, node);
        };

        // Remove node in the nodes and selectedNodes list.
        NodesManager.prototype._removeNode = function(system_id) {
            var idx = getIndexOfNode(this._nodes, system_id);
            if(idx >= 0) {
                this._updateMetadata(this._nodes[idx], METADATA_ACTIONS.DELETE);
            }
            removeNodeByIdFromArray(this._nodes, system_id);
            removeNodeByIdFromArray(this._selectedNodes, system_id);
        };

        // Get the node from the region.
        NodesManager.prototype.getNode = function(system_id) {
            var self = this;
            return RegionConnection.callMethod(
                "node.get", { system_id: system_id }).then(function(node) {
                    self._replaceNode(node);
                    return node;
                });
        };

        // Send the update information to the region.
        NodesManager.prototype.updateNode = function(node) {
            var self = this;
            node = angular.copy(node);
            delete node.$selected;
            return RegionConnection.callMethod(
                "node.update", node).then(function(node) {
                    self._replaceNode(node);
                    return node;
                });
        };

        // Send the delete call for node to the region.
        NodesManager.prototype.deleteNode = function(node) {
            var self = this;
            return RegionConnection.callMethod(
                "node.delete", { system_id: node.system_id }).then(function() {
                    self._removeNode(node.system_id);
                });
        };

        // True when the node list is stable and not being loaded or reloaded.
        NodesManager.prototype.canProcessActions = function() {
            return !this._isLoading;
        };

        // Handle notify from RegionConnection about a node.
        NodesManager.prototype.onNotify = function(action, data) {
            // Place the notification in the action queue.
            this._actionQueue.push({
                action: action,
                data: data
            });
            // Processing incoming actions is enabled. Otherwise they
            // will be queued until processActions is called.
            if(this.canProcessActions()) {
               $rootScope.$apply(this.processActions());
            }
        };

        // Process all actions to keep the node information up-to-date.
        NodesManager.prototype.processActions = function() {
            while(this._actionQueue.length > 0) {
                var action = this._actionQueue.shift();
                if(action.action === "create") {
                    action.data.$selected = false;
                    this._updateMetadata(
                        action.data, METADATA_ACTIONS.CREATE);
                    this._nodes.push(action.data);
                } else if(action.action === "update") {
                    this._replaceNode(action.data);
                } else if(action.action === "delete") {
                    this._removeNode(action.data);
                }
            }
        };

        // Return the active node.
        NodesManager.prototype.getActiveNode = function() {
            return this._activeNode;
        };

        // Set the active node.
        NodesManager.prototype.setActiveNode = function(node) {
            var self = this;
            this._activeNode = null;
            return this.getNode(node.system_id).then(function(node) {
                self._activeNode = node;
                return node;
            });
        };

        // Return list of selected nodes.
        NodesManager.prototype.getSelectedNodes = function(node) {
            return this._selectedNodes;
        };

        // Mark the given node as selected.
        NodesManager.prototype.selectNode = function(system_id) {
            var idx = getIndexOfNode(this._nodes, system_id);
            if(idx === -1) {
                console.log(
                    "WARN: selection of node(" + system_id +
                    ") failed because its missing in the nodes list.");
                return;
            }

            var node = this._nodes[idx];
            node.$selected = true;

            idx = this._selectedNodes.indexOf(node);
            if(idx === -1) {
                this._selectedNodes.push(node);
            }
        };

        // Mark the given node as unselected.
        NodesManager.prototype.unselectNode = function(system_id) {
            var idx = getIndexOfNode(this._nodes, system_id);
            if(idx === -1) {
                console.log(
                    "WARN: de-selection of node(" + system_id +
                    ") failed because its missing in the nodes list.");
                return;
            }

            var node = this._nodes[idx];
            node.$selected = false;

            idx = this._selectedNodes.indexOf(node);
            if(idx >= 0) {
                this._selectedNodes.splice(idx, 1);
            }
        };

        // Determine if a node is selected.
        NodesManager.prototype.isSelected = function(system_id) {
            var idx = getIndexOfNode(this._nodes, system_id);
            if(idx === -1) {
                console.log(
                    "WARN: unable to determine if node(" + system_id +
                    ") is selected because its missing in the nodes list.");
                return false;
            }

            return this._nodes[idx].$selected === true;
        };

        // Return all the metadata object.
        NodesManager.prototype.getMetadata = function() {
            return this._metadata;
        };

        // Update the metadata objects based on the given node and action.
        NodesManager.prototype._updateMetadata = function(node, action) {
            var oldNode, idx;
            if(action === METADATA_ACTIONS.UPDATE) {
                // Update actions require the oldNode if it exist in the
                // current node listing.
                idx = getIndexOfNode(this._nodes, node.system_id);
                if(idx >= 0) {
                    oldNode = this._nodes[idx];
                }
            }
            updateMetadata(
                this._metadata.statuses, node, 'status', action, oldNode);
            updateMetadata(
                this._metadata.owners, node, 'owner', action, oldNode);
        };

        return new NodesManager();
    }]);
