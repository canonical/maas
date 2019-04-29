/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS PackageRepositories Manager
 *
 * Manages all of the PackageRepositories in the browser. The manager uses the
 * RegionConnection to load the PackageRepositories, update them, and listen
 * for notification events about them.
 */

function PackageRepositoriesManager(RegionConnection, Manager) {
  function PackageRepositoriesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "packagerepository";

    // Listen for notify events for the PackageRepository object.
    var self = this;
    RegionConnection.registerNotifier("packagerepository", function(
      action,
      data
    ) {
      self.onNotify(action, data);
    });
  }

  PackageRepositoriesManager.prototype = new Manager();

  // Create the repository.
  PackageRepositoriesManager.prototype.create = function(repository) {
    return RegionConnection.callMethod(
      this._handler + ".create",
      repository,
      true
    );
  };

  return new PackageRepositoriesManager();
}

PackageRepositoriesManager.$inject = ["RegionConnection", "Manager"];

export default PackageRepositoriesManager;
