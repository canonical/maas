/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Event Manager Factory
 *
 * Manages all of the events for a node in the browser. The manager uses the
 * RegionConnection to load the events and listen for event notifications.
 */

function EventsManagerFactory(RegionConnection, Manager) {
  function EventsManager(nodeId, factory) {
    Manager.call(this);

    this._pk = "id";
    this._handler = "event";
    this._nodeId = nodeId;
    this._factory = factory;
    this._maxDays = 1;
  }

  EventsManager.prototype = new Manager();

  // Return the initial batch parameters with the id of the node
  // and the maximum number of days to load.
  EventsManager.prototype._initBatchLoadParameters = function() {
    return {
      node_id: this._nodeId,
      max_days: this._maxDays
    };
  };

  // Destroys its self. Removes self from the EventsManagerFactory.
  EventsManager.prototype.destroy = function() {
    this._factory.destroyManager(this);

    // If this manager has ever loaded then the region is sending
    // events about this node. Tell the RegionConnection not to
    // stop sending notification for events from this node.
    if (this.isLoaded()) {
      RegionConnection.callMethod("event.clear", {
        node_id: this._nodeId
      });
    }
  };

  // Get the maximum number of days the manager will load.
  EventsManager.prototype.getMaximumDays = function() {
    return this._maxDays;
  };

  // Changes the maximum number of days to load and loads the items.
  EventsManager.prototype.loadMaximumDays = function(days) {
    var self = this;
    var setMaximumDays = function() {
      self._maxDays = days;
      self.loadItems();
    };

    if (this.isLoading()) {
      // Call loadItems to get an extra defer to know when
      // the loading is done.
      this.loadItems().then(function() {
        setMaximumDays();
      });
    } else {
      setMaximumDays();
    }
  };

  // Factory that holds all created EventsManagers.
  function EventsManagerFactory() {
    // Holds a list of all EventsManager that have been created.
    this._managers = [];

    // Listen for notify events for the event object.
    var self = this;
    RegionConnection.registerNotifier("event", function(action, data) {
      self.onNotify(action, data);
    });
  }

  // Gets the EventManager for the nodes with node_id.
  EventsManagerFactory.prototype._getManager = function(nodeId) {
    var i;
    for (i = 0; i < this._managers.length; i++) {
      if (this._managers[i]._nodeId === nodeId) {
        return this._managers[i];
      }
    }
    return null;
  };

  // Gets the EventManager for the nodes node_id. Creates a new manager
  // if one does not exist.
  EventsManagerFactory.prototype.getManager = function(nodeId) {
    var manager = this._getManager(nodeId);
    if (!angular.isObject(manager)) {
      // Not created so create it.
      manager = new EventsManager(nodeId, this);
      this._managers.push(manager);
      return manager;
    }
    return manager;
  };

  // Destroy the EventManager.
  EventsManagerFactory.prototype.destroyManager = function(manager) {
    var idx = this._managers.indexOf(manager);
    if (idx >= 0) {
      this._managers.splice(idx, 1);
    }
  };

  // Called when the RegionConnection gets a notification for an event.
  EventsManagerFactory.prototype.onNotify = function(action, data) {
    if (action === "delete") {
      // Send all delete actions to all managers. Only one will
      // remove the event with the given id.
      angular.forEach(this._managers, function(manager) {
        manager.onNotify(action, data);
      });
    } else if (action === "create" || action === "update") {
      // Get the manager based on the node_id in data, and send
      // it the notification.
      var manager = this._getManager(data.node_id);
      if (angular.isObject(manager)) {
        manager.onNotify(action, data);
      }
    }
  };

  return new EventsManagerFactory();
}

EventsManagerFactory.$inject = ["RegionConnection", "Manager"];

export default EventsManagerFactory;
