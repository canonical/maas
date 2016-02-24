/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by VLAN.
 */

angular.module('MAAS').filter('filterByVLAN', function() {
    return function(subnets, vlan) {
        var filtered = [];
        if(!angular.isObject(vlan)) {
            return filtered;
        }
        angular.forEach(subnets, function(subnet) {
            if(subnet.vlan === vlan.id) {
                filtered.push(subnet);
            }
        });
        return filtered;
    };
});

angular.module('MAAS').filter('filterSpacesByVLAN', function() {
    return function(spaces, vlan) {
        var filtered = [];
        if(!angular.isObject(vlan)) {
            return filtered;
        }
        angular.forEach(spaces, function(space) {
            if(vlan.space_ids.indexOf(space.id) !== -1) {
                filtered.push(space);
            }
        });
        return filtered;
    };
});

angular.module('MAAS').filter('filterControllersByVLAN', function() {
    return function(controllers, vlan) {
        var filtered = [];
        if(!angular.isObject(vlan)) {
            return filtered;
        }
        angular.forEach(controllers, function(controller) {
            // XXX mpontillo hack since controllers lack interfaces for now
            // if(controller.vlan_ids.indexOf(vlan.id) != -1) {
                filtered.push(controller);
            //}
        }
        );
        return filtered;
    };
});