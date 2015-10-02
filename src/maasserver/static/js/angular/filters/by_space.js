/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by Space.
 */

angular.module('MAAS').filter('filterBySpace', function() {
    return function(subnets, space) {
        var filtered = [];
        if(!angular.isObject(space)) {
            return filtered;
        }
        angular.forEach(subnets, function(subnet) {
            if(subnet.space === space.id) {
                filtered.push(subnet);
            }
        });
        return filtered;
    };
});
