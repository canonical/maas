/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter VLANs by Fabric.
 */

function filterByFabric() {
  return function(vlans, fabric) {
    var filtered = [];
    var id;
    if (angular.isObject(fabric)) {
      id = fabric.id;
    } else if (angular.isNumber(fabric)) {
      id = fabric;
    } else {
      return filtered;
    }
    angular.forEach(vlans, function(vlan) {
      if (vlan.fabric === id) {
        filtered.push(vlan);
      }
    });
    return filtered;
  };
}

export default filterByFabric;
