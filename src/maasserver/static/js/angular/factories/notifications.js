/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Notifications Manager.
 *
 * Manages notifications in the browser. Uses RegionConnection to load
 * notifications, await new, updated, and deleted notifications, and to
 * dismiss them.
 */

function NotificationsManager(RegionConnection, Manager) {
  function NotificationsManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "notification";

    // Listen for notify events for the notification object.
    RegionConnection.registerNotifier(
      "notification",
      angular.bind(this, this.onNotify)
    );
  }

  NotificationsManager.prototype = new Manager();
  NotificationsManager.prototype.dismiss = function(notification) {
    return RegionConnection.callMethod("notification.dismiss", {
      id: notification.id
    });
  };

  return new NotificationsManager();
}

NotificationsManager.$inject = ["RegionConnection", "Manager"];

export default NotificationsManager;
