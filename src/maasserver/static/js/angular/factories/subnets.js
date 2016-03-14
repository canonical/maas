/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Subnet Manager
 *
 * Manages all of the subnets in the browser. The manager uses the
 * RegionConnection to load the subnets, update the subnets, and listen for
 * notification events about subnets.
 */

angular.module('MAAS').factory(
    'SubnetsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function SubnetsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "subnet";

            // Listen for notify events for the subnet object.
            var self = this;
            RegionConnection.registerNotifier("subnet",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        SubnetsManager.prototype = new Manager();

        // Return the name of the subnet. Will include the name of the subnet
        // in '(', ')' if it exists and not the same as the cidr.
        SubnetsManager.prototype.getName = function(subnet) {
            if(!angular.isObject(subnet)) {
                return "";
            }

            var name = subnet.cidr;
            if(angular.isString(subnet.name) &&
                subnet.name !== "" &&
                subnet.name !== subnet.cidr) {
                name += " (" + subnet.name + ")";
            }
            return name;
        };

        SubnetsManager.prototype.getLargestRange = function(subnet) {
            var largest_range = {num_addresses: 0, start: "", end: ""};
            angular.forEach(subnet.statistics.ranges, function(iprange) {
                if(angular.equals(iprange.purpose, ["unused"]) &&
                        iprange.num_addresses > largest_range.num_addresses) {
                    largest_range = iprange;
                }
            });
            return largest_range;
        };

        SubnetsManager.prototype.hasDynamicRange = function(subnet) {
            var i;
            for(i = 0; i < subnet.statistics.ranges.length ; i++) {
                var iprange = subnet.statistics.ranges[i];
                if(iprange.purpose.indexOf("dynamic") !== -1) {
                    return true;
                }
            }
            return false;
        };


        return new SubnetsManager();
    }]);
