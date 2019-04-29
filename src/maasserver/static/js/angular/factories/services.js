/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Service Manager
 *
 * Manages all of the services for a node in the browser. The manager uses the
 * RegionConnection to load the services and listen for service notifications.
 */

function ServicesManager(RegionConnection, Manager) {
  function ServicesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "service";

    // Listen for notify events for the service object.
    var self = this;
    RegionConnection.registerNotifier("service", function(action, data) {
      self.onNotify(action, data);
    });
  }

  ServicesManager.prototype = new Manager();

  return new ServicesManager();
}

ServicesManager.$inject = ["RegionConnection", "Manager"];

export default ServicesManager;
