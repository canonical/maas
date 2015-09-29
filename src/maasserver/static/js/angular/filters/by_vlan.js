/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by VLAN.
 */

angular.module('MAAS').filter('filterByVLAN', function() {
    return function(subnets, vlan) {
        var filtered = [];
        angular.forEach(subnets, function(subnet) {
            if(subnet.vlan === vlan.id) {
                filtered.push(subnet);
            }
        });
        return filtered;
    };
});
