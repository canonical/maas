/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by VLAN.
 */

angular.module('MAAS').filter('orderByDate', function() {
    return function(items, field, field2) {
        var sorted = items.slice();
        sorted.sort(function(a, b) {
            aDate = new Date(a[field]);
            bDate = new Date(b[field]);

            // Sort by ID as well if equal.
            if(angular.isString(field2) &&
                aDate.getTime() === bDate.getTime()) {
                return (
                    a[field2] > b[field2] ? -1 : a[field2] < b[field2] ? 1 : 0);
            } else {
              return aDate > bDate ? -1 : aDate < bDate ? 1 : 0;
            }
        });
        return sorted;
    };
});
