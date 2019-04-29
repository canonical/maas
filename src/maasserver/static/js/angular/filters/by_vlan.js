/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter Subnets by VLAN.
 */

export function filterByVLAN() {
  return function(subnets, vlan) {
    var filtered = [];
    var id;
    if (angular.isObject(vlan)) {
      id = vlan.id;
    } else if (angular.isNumber(vlan)) {
      id = vlan;
    } else {
      return filtered;
    }
    angular.forEach(subnets, function(subnet) {
      if (subnet.vlan === id) {
        filtered.push(subnet);
      }
    });
    return filtered;
  };
}

export function filterControllersByVLAN() {
  return function(controllers, vlan) {
    var filtered = [];
    if (!angular.isObject(vlan)) {
      return filtered;
    }
    angular.forEach(controllers, function(controller) {
      // XXX mpontillo disable VLAN check until VLAN is populated
      // on the rack controller's interfaces.
      // if(controller.vlan_ids.indexOf(vlan.id) != -1) {

      // XXX mpontillo 2016-02-22 this is a hack to prevent too many
      // nodes from being sent through the filter; we have a bug which
      // sends nodes in which are not controllers.
      if (controller.node_type === 2 || controller.node_type === 4) {
        filtered.push(controller);
      }
    });
    return filtered;
  };
}
