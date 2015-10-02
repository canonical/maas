/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter VLANs by Fabric.
 */

angular.module('MAAS').filter('filterByFabric', function() {
    return function(vlans, fabric) {
        var filtered = [];
        if(!angular.isObject(fabric)) {
            return filtered;
        }
        angular.forEach(vlans, function(vlan) {
            if(vlan.fabric === fabric.id) {
                filtered.push(vlan);
            }
        });
        return filtered;
    };
});
