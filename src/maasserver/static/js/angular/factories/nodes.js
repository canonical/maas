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
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function NodesManager() {
            Manager.call(this);

            this._pk = "system_id";
            this._handler = "node";
            this._metadataAttributes = {
                "status": null,
                "owner": null,
                "tags": null,
                "zone": function(node) {
                    return node.zone.name;
                },
                "networks": null,
                "storage_tags": null
            };

            // Listen for notify events for the node object.
            var self = this;
            RegionConnection.registerNotifier("node", function(action, data) {
                self.onNotify(action, data);
            });
        }

        NodesManager.prototype = new Manager();

        // Create a node.
        NodesManager.prototype.create = function(node) {
            // We don't add the item to the list because a NOTIFY event will
            // add the node to the list. Adding it here will cause angular to
            // complain because the same object exist in the list.
            return RegionConnection.callMethod("node.create", node);
        };

        // Perform the action on the node.
        NodesManager.prototype.performAction = function(node, action, extra) {
            if(!angular.isObject(extra)) {
                extra = {};
            }
            return RegionConnection.callMethod("node.action", {
                "system_id": node.system_id,
                "action": action,
                "extra": extra
                });
        };

        // Check the power state for the node.
        NodesManager.prototype.checkPowerState = function(node) {
            return RegionConnection.callMethod("node.check_power", {
                "system_id": node.system_id
                }).then(function(state) {
                    node.power_state = state;
                    return state;
                }, function(error) {
                    node.power_state = "error";

                    // Already been logged server side, but log it client
                    // side so if they really care they can see why.
                    console.log(error);

                    // Return the state as error to the remaining callbacks.
                    return "error";
                });
        };

        // Create the VLAN interface on the node.
        NodesManager.prototype.createVLANInterface = function(
            node, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = node.system_id;
                return RegionConnection.callMethod(
                    "node.create_vlan", params);
            };

        // Update the interface for the node.
        NodesManager.prototype.updateInterface = function(
            node, interface_id, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = node.system_id;
                params.interface_id = interface_id;
                return RegionConnection.callMethod(
                    "node.update_interface", params);
            };

        // Delete the interface for the node.
        NodesManager.prototype.deleteInterface = function(
            node, interface_id) {
                var params = {
                    system_id: node.system_id,
                    interface_id: interface_id
                };
                return RegionConnection.callMethod(
                    "node.delete_interface", params);
            };

        // Create or update the link to the subnet for the interface.
        NodesManager.prototype.linkSubnet = function(
            node, interface_id, params) {
                if(!angular.isObject(params)) {
                    params = {};
                }
                params.system_id = node.system_id;
                params.interface_id = interface_id;
                return RegionConnection.callMethod(
                    "node.link_subnet", params);
            };

        // Remove the link to the subnet for the interface.
        NodesManager.prototype.unlinkSubnet = function(
            node, interface_id, link_id) {
                var params = {
                    system_id: node.system_id,
                    interface_id: interface_id,
                    link_id: link_id
                };
                return RegionConnection.callMethod(
                    "node.unlink_subnet", params);
            };

        // Unmount the filesystem on the block device or partition.
        NodesManager.prototype.unmountFilesystem = function(
            system_id, block_id, partition_id) {
                var self = this;
                var method = this._handler + ".unmount_filesystem";
                var params = {
                    system_id: system_id,
                    block_id: block_id,
                    partition_id: partition_id
                };
                return RegionConnection.callMethod(method, params);
            };

        return new NodesManager();
    }]);
