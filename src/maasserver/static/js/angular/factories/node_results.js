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
    'NodeResultsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager',
    function($q, $rootScope, RegionConnection, Manager) {

        function NodeResultsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "noderesult";

            // Listen for notify events for the ScriptResult object.
            var self = this;
            RegionConnection.registerNotifier("scriptresult",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        NodeResultsManager.prototype = new Manager();

        // Get result data.
        NodeResultsManager.prototype.get_result_data = function(
            script_id, data_type) {
            var method = this._handler + ".get_result_data";
            var params = {
                script_id: script_id,
                data_type: data_type
            };
            return RegionConnection.callMethod(method, params);
        };

        return new NodeResultsManager();
    }]);
