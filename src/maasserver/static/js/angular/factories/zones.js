/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Zone Manager
 *
 * Manages all of the zones in the browser. The manager uses the
 * RegionConnection to load the zones, update the zones, and listen for
 * notification events about zones.
 */

function ZonesManager(RegionConnection, Manager) {
  function ZonesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "zone";

    // Listen for notify events for the zone object.
    var self = this;
    RegionConnection.registerNotifier("zone", function(action, data) {
      self.onNotify(action, data);
    });
  }

  ZonesManager.prototype = new Manager();

  // Return the default zone.
  ZonesManager.prototype.getDefaultZone = function(pod) {
    var zoneId = 0;
    var i;
    var itemsLength = this._items.length;

    if (pod) {
      zoneId = pod.zone;
    }

    if (itemsLength === 0) {
      return null;
    }

    for (i = 0; i < itemsLength; i++) {
      if (this._items[i].id === zoneId) {
        return this._items[i];
      }
    }

    return this._items[0];
  };

  return new ZonesManager();
}

ZonesManager.$inject = ["RegionConnection", "Manager"];

export default ZonesManager;
