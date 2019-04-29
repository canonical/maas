/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Switches Manager
 *
 * Manages all of the switches in the browser. This manager is used for the
 * switches listing and the switches view page. The manager uses the
 * RegionConnection to load the switches, update the switches, and listen for
 * notification events about switches.
 */

function SwitchesManager(RegionConnection, NodesManager) {
  function SwitchesManager() {
    NodesManager.call(this);

    this._pk = "system_id";
    this._handler = "switch";
    this._metadataAttributes = {
      owner: null,
      subnets: null,
      tags: null,
      zone: function(device) {
        return device.zone.name;
      }
    };

    // Listen for notify events for the switch object.
    var self = this;
    RegionConnection.registerNotifier("switch", function(action, data) {
      self.onNotify(action, data);
    });
  }

  SwitchesManager.prototype = new NodesManager();

  // Create a switch.
  SwitchesManager.prototype.create = function(node) {
    // We don't add the item to the list because a NOTIFY event will
    // add the device to the list. Adding it here will cause angular to
    // complain because the same object exist in the list.
    return RegionConnection.callMethod("switch.create", node);
  };

  // Perform the action on the switch.
  SwitchesManager.prototype.performAction = function(device, action, extra) {
    if (!angular.isObject(extra)) {
      extra = {};
    }
    return RegionConnection.callMethod("switch.action", {
      system_id: device.system_id,
      action: action,
      extra: extra
    });
  };

  return new SwitchesManager();
}

SwitchesManager.$inject = ["RegionConnection", "NodesManager"];

export default SwitchesManager;
