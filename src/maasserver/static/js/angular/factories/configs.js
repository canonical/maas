/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Configs Manager
 *
 * Manages all of the config values in the browser. This manager is used for
 * the first-user journey and the settings page.
 */

function ConfigsManager(RegionConnection, Manager) {
  function ConfigsManager() {
    Manager.call(this);

    this._pk = "name";
    this._handler = "config";

    // Listen for notify events for the config object.
    var self = this;
    RegionConnection.registerNotifier("config", function(action, data) {
      self.onNotify(action, data);
    });
  }

  ConfigsManager.prototype = new Manager();

  return new ConfigsManager();
}

ConfigsManager.$inject = ["RegionConnection", "Manager"];

export default ConfigsManager;
