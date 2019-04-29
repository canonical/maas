/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Fabric Manager
 *
 * Manages all of the fabrics in the browser. The manager uses the
 * RegionConnection to load the fabrics, update the fabrics, and listen for
 * notification events about fabrics.
 */

function FabricsManager(RegionConnection, Manager) {
  function FabricsManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "fabric";

    // Listen for notify events for the fabric object.
    var self = this;
    RegionConnection.registerNotifier("fabric", function(action, data) {
      self.onNotify(action, data);
    });
  }

  FabricsManager.prototype = new Manager();

  // Given a Fabric object, returns its display name.
  FabricsManager.prototype.getName = function(fabric) {
    if (!angular.isObject(fabric)) {
      return;
    }
    if (angular.isString(fabric.name)) {
      return fabric.name;
    } else {
      return this._handler + "-" + fabric[this._pk];
    }
  };

  // Delete the Fabric.
  FabricsManager.prototype.deleteFabric = function(fabric) {
    return RegionConnection.callMethod(
      "fabric.delete",
      { id: fabric.id },
      true
    );
  };

  // Create a Fabric.
  FabricsManager.prototype.create = function(fabric) {
    // We don't add the item to the list because a NOTIFY event will
    // add the domain to the list. Adding it here will cause angular to
    // complain because the same object exist in the list.
    return RegionConnection.callMethod("fabric.create", fabric);
  };

  return new FabricsManager();
}

FabricsManager.$inject = ["RegionConnection", "Manager"];

export default FabricsManager;
