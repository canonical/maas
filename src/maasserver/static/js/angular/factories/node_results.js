/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS NodeResultsManager Manager
 *
 * Manages all of the NodeResults in the browser. The manager uses the
 * RegionConnection to load the NodeResults, and listen for
 * notification events about NodeResults.
 */

angular.module('MAAS').factory(
    'NodeResultsManagerFactory', ['RegionConnection', 'Manager',
    function(RegionConnection, Manager) {

        function NodeResultsManager(node_system_id, factory) {
            Manager.call(this);

            this._pk = "id";
            this._handler = "noderesult";
            this._node_system_id = node_system_id;
            this._factory = factory;

            // Listen for notify events for the ScriptResult object.
            var self = this;
            RegionConnection.registerNotifier("scriptresult",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        NodeResultsManager.prototype = new Manager();

        // Return the list of ScriptResults for the given node when retrieving
        // the initial list.
        NodeResultsManager.prototype._initBatchLoadParameters = function() {
            var ret = {
                "system_id": this._node_system_id
            };
            if(this._result_type === 'testing') {
                ret.result_type = 2;
            }else if(this._result_type === 'commissioning') {
                ret.result_type = 0;
            }else if(this._result_type === 'installation') {
                ret.result_type = 1;
            }
            return ret;
        };

        // Get result data.
        NodeResultsManager.prototype.get_result_data = function(
            script_id, data_type) {
            var method = this._handler + ".get_result_data";
            var params = {
                id: script_id,
                data_type: data_type
            };
            return RegionConnection.callMethod(method, params);
        };

        // Factory that holds all created NodeResultsManagers.
        function NodeResultsManagerFactory() {
            // Holds a list of all NodeResultsManagers that have been created.
            this._managers = [];
        }

        // Gets the NodeResultsManager for the nodes with node_system_id.
        NodeResultsManagerFactory.prototype._getManager = function(
                 node_system_id) {
            var i;
            for(i = 0; i < this._managers.length; i++) {
                if(this._managers[i]._node_system_id === node_system_id) {
                    return this._managers[i];
                }
            }
            return null;
        };

        // Gets the NodeResultsManager for the nodes system_id. Creates a new
        // manager if one does not exist.
        NodeResultsManagerFactory.prototype.getManager = function(
                node_system_id, result_type) {
            var manager = this._getManager(node_system_id);
            if(!angular.isObject(manager)) {
                // Not created so create it.
                manager = new NodeResultsManager(node_system_id, this);
                this._managers.push(manager);
            }
            manager._result_type = result_type;
            return manager;
        };

        return new NodeResultsManagerFactory();
    }]);
