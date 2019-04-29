/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Controllers Manager
 *
 * Manages all of the controllers in the browser. This manager is used for the
 * controller listing and view pages. The manager is a subclass of
 * NodesManager.
 */

function ControllersManager(RegionConnection, NodesManager, ServicesManager) {
  function ControllersManager() {
    NodesManager.call(this);

    this._pk = "system_id";
    this._handler = "controller";

    // Listen for notify events for the controller object.
    var self = this;
    RegionConnection.registerNotifier("controller", function(action, data) {
      self.onNotify(action, data);
    });
  }
  ControllersManager.prototype = new NodesManager();

  ControllersManager.prototype.getServices = function(controller) {
    var services = [];
    angular.forEach(controller.service_ids, function(service_id) {
      var service = ServicesManager.getItemFromList(service_id);
      if (angular.isObject(service)) {
        services.push(service);
      }
    });
    return services;
  };

  // Check the boot image import status.
  ControllersManager.prototype.checkImageStates = function(controllers) {
    return RegionConnection.callMethod(
      this._handler + ".check_images",
      controllers
    );
  };

  return new ControllersManager();
}

ControllersManager.$inject = [
  "RegionConnection",
  "NodesManager",
  "ServicesManager"
];

export default ControllersManager;
