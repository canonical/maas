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
            // XXX mpontillo disable VLAN check until VLAN is populated
            // on the rack controller's interfaces.
            // if(controller.vlan_ids.indexOf(vlan.id) != -1) {

            // XXX mpontillo 2016-02-22 this is a hack to prevent too many
            // nodes from being sent through the filter; we have a bug which
            // sends nodes in which are not controllers.
            if(controller.node_type === 2 || controller.node_type === 4) {
                filtered.push(controller);
            }
        });
        return filtered;
    };
});