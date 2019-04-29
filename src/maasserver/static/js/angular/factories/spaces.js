/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Space Manager
 *
 * Manages all of the spaces in the browser. The manager uses the
 * RegionConnection to load the spaces, update the spaces, and listen for
 * notification events about spaces.
 */

function SpacesManager(RegionConnection, Manager) {
  function SpacesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "space";

    // Listen for notify events for the space object.
    var self = this;
    RegionConnection.registerNotifier("space", function(action, data) {
      self.onNotify(action, data);
    });
  }

  SpacesManager.prototype = new Manager();

  // Create a space.
  SpacesManager.prototype.create = function(space) {
    // We don't add the item to the list because a NOTIFY event will
    // add the domain to the list. Adding it here will cause angular to
    // complain because the same object exist in the list.
    return RegionConnection.callMethod("space.create", space);
  };

  // Delete the space.
  SpacesManager.prototype.deleteSpace = function(space) {
    return RegionConnection.callMethod("space.delete", space);
  };

  return new SpacesManager();
}

SpacesManager.$inject = ["RegionConnection", "Manager"];

export default SpacesManager;
