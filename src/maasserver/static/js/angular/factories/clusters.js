/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Clusters Manager
 *
 * Manages all of the clusters in the browser. The manager uses the
 * RegionConnection to load the clusters, update the clusters, and listen for
 * notification events about clusters.
 */

angular.module('MAAS').factory(
    'ClustersManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function ClustersManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "cluster";

            // Listen for notify events for the cluster object.
            var self = this;
            RegionConnection.registerNotifier("cluster",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        ClustersManager.prototype = new Manager();

        return new ClustersManager();
    }]);
