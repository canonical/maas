/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS StaticRoute Manager
 *
 * Manages all of the StaticRoutes in the browser. The manager uses the
 * RegionConnection to load the StaticRoutes, update the StaticRoutes, and
 * listen for notification events about StaticRoutes.
 */

function StaticRoutesManager(RegionConnection, Manager) {
  function StaticRoutesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "staticroute";

    // Listen for notify events for the staticroute object.
    var self = this;
    RegionConnection.registerNotifier("staticroute", function(action, data) {
      self.onNotify(action, data);
    });
  }

  StaticRoutesManager.prototype = new Manager();

  return new StaticRoutesManager();
}

StaticRoutesManager.$inject = ["RegionConnection", "Manager"];

export default StaticRoutesManager;
