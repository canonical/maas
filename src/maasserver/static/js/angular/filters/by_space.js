/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by Space.
 */

export function filterBySpace() {
  return function(objects, space) {
    var filtered = [];
    var id;
    if (angular.isObject(space)) {
      id = space.id;
    } else if (angular.isNumber(space)) {
      id = space;
    } else {
      return filtered;
    }
    angular.forEach(objects, function(object) {
      if (object.space === id) {
        filtered.push(object);
      }
    });
    return filtered;
  };
}

export function filterByNullSpace() {
  return function(objects) {
    var filtered = [];
    angular.forEach(objects, function(object) {
      if (object.space === null) {
        filtered.push(object);
      }
    });
    return filtered;
  };
}
