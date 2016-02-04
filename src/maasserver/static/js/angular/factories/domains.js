/* Copyright 2015,2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domain Manager
 *
 * Manages all of the domains in the browser. The manager uses the
 * RegionConnection to load the domains, update the domains, and listen for
 * notification events about domains.
 */

angular.module('MAAS').factory(
    'DomainsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function DomainsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "domain";

            // Listen for notify events for the domain object.
            var self = this;
            RegionConnection.registerNotifier("domain",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        DomainsManager.prototype = new Manager();

        return new DomainsManager();
    }]);
