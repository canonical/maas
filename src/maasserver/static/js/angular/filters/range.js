/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Filter create range of integers
 */

function range() {
  return function(n) {
    var res = [];
    if (typeof n != "number") {
      return res;
    }
    for (var i = 0; i < n; i++) {
      res.push(i);
    }
    return res;
  };
}

export default range;
