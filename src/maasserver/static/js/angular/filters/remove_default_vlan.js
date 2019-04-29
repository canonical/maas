/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter to remove the default VLAN as an option.
 */

function removeDefaultVLAN() {
  return function(vlans) {
    var filtered = [];
    angular.forEach(vlans, function(vlan) {
      if (vlan.vid !== 0) {
        filtered.push(vlan);
      }
    });
    return filtered;
  };
}

export default removeDefaultVLAN;
