/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS SSHKey Manager
 *
 * Manages all of the SSHKeys in the browser. The manager uses the
 * RegionConnection to load the SSHKeys, update the SSHKeys, and
 * listen for notification events about SSHKeys.
 */

function SSHKeysManager(RegionConnection, Manager) {
  function SSHKeysManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "sshkey";

    // Listen for notify events for the sshkey object.
    var self = this;
    RegionConnection.registerNotifier("sshkey", function(action, data) {
      self.onNotify(action, data);
    });
  }

  SSHKeysManager.prototype = new Manager();

  // Imports SSH keys from a launchpad and github.
  SSHKeysManager.prototype.importKeys = function(params) {
    // We don't add the results to the list because a NOTIFY event will
    // add the ssh key to the list. Adding it here will cause angular
    // to complain because the same object exist in the list.
    return RegionConnection.callMethod("sshkey.import_keys", params);
  };

  return new SSHKeysManager();
}

SSHKeysManager.$inject = ["RegionConnection", "Manager"];

export default SSHKeysManager;
