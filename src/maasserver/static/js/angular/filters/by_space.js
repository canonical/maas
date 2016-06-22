/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by Space.
 */

angular.module('MAAS').filter('filterBySpace', function() {
    return function(subnets, space) {
        var filtered = [];
        var id;
        if(angular.isObject(space)) {
            id = space.id;
        } else if(angular.isNumber(space)) {
            id = space;
        } else {
            return filtered;
        }
        angular.forEach(subnets, function(subnet) {
            if(subnet.space === id) {
                filtered.push(subnet);
            }
        });
        return filtered;
    };
});
