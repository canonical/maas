/* Copyright 2016 Canonical Ltd.  This software is licensed under the
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

        // Create a domain.
        DomainsManager.prototype.create = function(domain) {
            // We don't add the item to the list because a NOTIFY event will
            // add the domain to the list. Adding it here will cause angular to
            // complain because the same object exist in the list.
            return RegionConnection.callMethod("domain.create", domain);
        };

        // Delete the domain.
        DomainsManager.prototype.deleteDomain = function(domain) {
            return RegionConnection.callMethod("domain.delete", domain);
        };

        // Create a DNS record.
        DomainsManager.prototype.createDNSRecord = function(record) {
            if(record.rrtype === 'A' || record.rrtype === 'AAAA') {
                record.ip_addresses = record.rrdata.split(/[ ,]+/);
                return RegionConnection.callMethod(
                    "domain.create_dnsresource", record);
            } else {
                return RegionConnection.callMethod(
                    "domain.create_dnsdata", record);
            }
        };

        DomainsManager.prototype.getDefaultDomain = function() {
            if(this._items.length === 0) {
                return null;
            } else {
                var i;
                for(i=0;i<this._items.length;i++) {
                    if(this._items[i].id === 0) {
                        return this._items[i];
                    }
                }
            }
            return this._items[0];
        };

        DomainsManager.prototype.getDomainByName = function(name) {
            if(this._items.length > 0) {
                var i;
                for(i=0;i<this._items.length;i++) {
                    if(this._items[i].name === name) {
                        return this._items[i];
                    }
                }
            }
            return null;
        };

        return new DomainsManager();
    }]);
