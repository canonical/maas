/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Discovery Manager
 *
 * A Discovery is a MAC, IP binding with an optional hostname that MAAS
 * believes it has discovered. It is associated with a particular fabric and
 * VLAN, and is aware of which rack or region interface most recently
 * discovered it.
 *
 * This class manages all of the discoveries in the browser. It uses the
 * RegionConnection to load the discoveries and listen for notification events
 * about discoveries.
 */

function DiscoveriesManager($q, RegionConnection, PollingManager) {
  function DiscoveriesManager() {
    PollingManager.call(this);

    this._pk = "first_seen";
    this._batchKey = "first_seen";
    this._handler = "discovery";

    // Poll every 10 seconds when its empty as its okay for
    // this to be empty.
    this._pollEmptyTimeout = 5000;
  }

  DiscoveriesManager.prototype = new PollingManager();

  DiscoveriesManager.prototype.removeDevice = function(device) {
    return RegionConnection.callMethod("discovery.delete_by_mac_and_ip", {
      ip: device.ip,
      mac: device.mac_address
    });
  };

  DiscoveriesManager.prototype.removeDevices = function(devices) {
    return $q.all(
      devices.map(function(device) {
        return RegionConnection.callMethod("discovery.delete_by_mac_and_ip", {
          ip: device.ip,
          mac: device.mac_address
        });
      })
    );
  };

  return new DiscoveriesManager();
}

DiscoveriesManager.$inject = ["$q", "RegionConnection", "PollingManager"];

export default DiscoveriesManager;
