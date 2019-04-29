/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Resource Pool Manager
 *
 * Manages all of the resource pools in the browser.
 */

function ResourcePoolsManager(RegionConnection, Manager) {
  function ResourcePoolsManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "resourcepool";

    // Listen for notify events for the resource pool object.
    var self = this;
    RegionConnection.registerNotifier("resourcepool", function(action, data) {
      self.onNotify(action, data);
    });
  }

  ResourcePoolsManager.prototype = new Manager();

  // Return the default pool.
  ResourcePoolsManager.prototype.getDefaultPool = function() {
    var i;
    for (i = 0; i < this._items.length; i++) {
      if (this._items[i].id === 0) {
        return this._items[i];
      }
    }
  };

  return new ResourcePoolsManager();
}

ResourcePoolsManager.$inject = ["RegionConnection", "Manager"];

export default ResourcePoolsManager;
