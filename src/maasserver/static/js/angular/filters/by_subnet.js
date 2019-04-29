/* Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Filter objects with subnet foreign key references by a particular subnet.
 */

export function filterBySubnet() {
  return function(foreign_objects, subnet, key) {
    var filtered = [];
    var id;
    if (angular.isObject(subnet)) {
      id = subnet.id;
    } else if (angular.isNumber(subnet)) {
      id = subnet;
    } else {
      return filtered;
    }
    if (angular.isUndefined(key)) {
      key = "subnet";
    }
    angular.forEach(foreign_objects, function(obj) {
      if (obj[key] === id) {
        filtered.push(obj);
      }
    });
    return filtered;
  };
}

// Filters by subnet, unless the subnet is not defined. If the subnet is not
// defined, filters by VLAN.
export function filterBySubnetOrVlan() {
  return function(foreign_objects, subnet, vlan) {
    var filtered = [];
    var id;
    var key = null;
    if (angular.isDefined(subnet) && subnet !== null) {
      key = "subnet";
      if (angular.isObject(subnet)) {
        id = subnet.id;
      } else if (angular.isNumber(subnet)) {
        id = subnet;
      }
    } else if (angular.isDefined(vlan) && vlan !== null) {
      key = "vlan";
      if (angular.isObject(vlan)) {
        id = vlan.id;
      } else if (angular.isNumber(vlan)) {
        id = vlan;
      }
    } else {
      return filtered;
    }
    angular.forEach(foreign_objects, function(obj) {
      if (obj[key] === id) {
        filtered.push(obj);
      }
    });
    return filtered;
  };
}
