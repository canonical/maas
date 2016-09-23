/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Discovery Manager
 *
 * A Discovery is a MAC, IP binding with an optional hostname that MAAS
 * believes it has discovered. It is associated with a particular fabric and
 * VLAN, and is aware of which rack or region interface most recently
 * discovered it.
 *
 * This class manages all of the discoveries in the browser. It uses the
 * RegionConnection to load the discoveries and listen for notification events
 * about discoveries.
 */

angular.module('MAAS').factory(
    'DiscoveriesManager',
    ['$q', '$rootScope', 'RegionConnection', 'PollingManager',
    function($q, $rootScope, RegionConnection, PollingManager) {

        function DiscoveriesManager() {
            PollingManager.call(this);

            this._pk = "discovery_id";
            this._handler = "discovery";

            // Poll every 10 seconds when its empty as its okay for
            // this to be empty.
            this._pollEmptyTimeout = 5000;
        }

        DiscoveriesManager.prototype = new PollingManager();

        return new DiscoveriesManager();
    }]);
