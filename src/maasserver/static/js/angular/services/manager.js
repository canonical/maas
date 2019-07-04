/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Base Manager
 *
 * Manages a collection of items from the websocket in the browser. The manager
 * uses the RegionConnection to load the items, update the items, and listen
 * for notification events about the items.
 */

/* @ngInject */
function Manager($q, $rootScope, $timeout, RegionConnection) {
  // Actions that are used to update the statuses metadata.
  var METADATA_ACTIONS = {
    CREATE: "create",
    UPDATE: "update",
    DELETE: "delete"
  };

  // Constructor
  function Manager() {
    // Primary key on the items in the list. Used to match items.
    this._pk = "id";

    // Key used when loading batches. Typically the same as _pk
    // but not always.
    this._batchKey = "id";

    // Number to load per batch.
    this._batchSize = 50;

    // The field from which to get a human-readable name.
    this._name_field = "name";

    // Handler on the region to call to list, create, update, delete,
    // and listen for notifications. Must be set by overriding manager.
    this._handler = null;

    // Holds all items in the system. This list must always be the same
    // object.
    this._items = [];

    // The way this manager receives its updated information. 'notify'
    // means this manager received notify messages from the websocket.
    // See PollingManager for the other possible type. This is only
    // used by the `ManagerHelperService` to identify how updating
    // the data should be handled.
    this._type = "notify";

    // Holds list of scopes that currently have this manager loaded.
    this._scopes = [];

    // True when all of the items have been loaded. This is done on
    // initial connection to the region.
    this._loaded = false;

    // True when the items list is currently being loaded or reloaded.
    // Actions will not be processed while this is false.
    this._isLoading = false;

    // Holds list of defers that need to be called once the loading of
    // items has finished. This is used when a caller calls loadItems
    // when its already loading.
    this._extraLoadDefers = [];

    // Holds list of defers that need to be called once the reloading
    // of items has finished. This is used when a caller calls
    // reloadItems when its already reloading.
    this._extraReloadDefers = [];

    // Holds all of the notify actions that need to be processed. This
    // is used to hold the actions while the items are being loaded.
    // Once all of the items are loaded the queue will be processed.
    this._actionQueue = [];

    // Holds list of all of the currently selected items. This is held
    // in a separate list to remove the need to loop through the full
    // listing to grab the selected items.
    this._selectedItems = [];

    // Set to true when the items list should reload upon re-connection
    // to the region.
    this._autoReload = false;

    // Holds the item that is currently being viewed. This object will
    // be updated if any notify events are received for it. This allows
    // the ability of not having to keep pulling the item out of the
    // items list.
    this._activeItem = null;

    // Holds metadata information that is used to helper filtering.
    this._metadata = {};

    // List of attributes to track on the loaded items. Each attribute
    // in this list will be placed in _metadata to track its current
    // values and the number of items with that value.
    this._metadataAttributes = [];
  }

  // Return index of the item in the given array.
  Manager.prototype._getIndexOfItem = function(array, pk_value) {
    var i;
    var len;
    for (i = 0, len = array.length; i < len; i++) {
      if (array[i][this._pk] === pk_value) {
        return i;
      }
    }
    return -1;
  };

  // Replace the item in the array at the same index.
  Manager.prototype._replaceItemInArray = function(array, item) {
    var idx = this._getIndexOfItem(array, item[this._pk]);
    if (idx >= 0) {
      // Keep the current selection on the item.
      item.$selected = array[idx].$selected;
      angular.copy(item, array[idx]);
    }
  };

  // Remove the item from the array.
  Manager.prototype._removeItemByIdFromArray = function(array, pk_value) {
    var idx = this._getIndexOfItem(array, pk_value);
    if (idx >= 0) {
      array.splice(idx, 1);
    }
  };

  // Return the parameters that should be used for the batch load
  // request. Should be used by subclass that want to add extra
  // parameters to the batch request. By default it returns an empty
  // object.
  Manager.prototype._initBatchLoadParameters = function() {
    return {};
  };

  // Batch load items from the region in groups of _batchSize.
  Manager.prototype._batchLoadItems = function(array, extra_func) {
    var self = this;
    var defer = $q.defer();
    var method = this._handler + ".list";
    function callLoad() {
      var params = self._initBatchLoadParameters();
      params.limit = self._batchSize;

      // Get the last batchKey in the list so the region knows to
      // start at that offset.
      if (array.length > 0) {
        params.start = array[array.length - 1][self._batchKey];
      }
      RegionConnection.callMethod(method, params).then(function(items) {
        // Pass each item to extra_func function if given.
        if (angular.isFunction(extra_func)) {
          angular.forEach(items, function(item) {
            extra_func(item);
          });
        }

        array.push.apply(array, items);
        if (items.length === self._batchSize) {
          // Could be more items, request the next batch.
          callLoad(array);
        } else {
          defer.resolve(array);
        }
      }, defer.reject);
    }
    callLoad();
    return defer.promise;
  };

  // Resolves array of defers with item.
  Manager.prototype._resolveDefers = function(defersArray, item) {
    angular.forEach(defersArray, function(defer) {
      defer.resolve(item);
    });
  };

  // Rejects array of defers with error.
  Manager.prototype._rejectDefers = function(defersArray, error) {
    angular.forEach(defersArray, function(defer) {
      defer.reject(error);
    });
  };

  // Return list of items.
  Manager.prototype.getItems = function() {
    return this._items;
  };

  // Clears the current state of the manager.
  Manager.prototype.clear = function() {
    this._loaded = false;
    this._items.length = 0;
    this._actionQueue.length = 0;
    this._selectedItems.length = 0;
    this._activeItem = null;
    this._metadata = {};
    this._metadataAttributes.length = 0;
  };

  // Clears the current state of the manager.
  Manager.prototype.clearItems = function() {
    this._loaded = false;
    this._items.length = 0;
    this._selectedItems.length = 0;
    this._activeItem = null;
  };

  // Load all the items.
  Manager.prototype.loadItems = function() {
    // If the items have already been loaded then, we need to
    // reload the items list not load the initial list.
    if (this._loaded) {
      return this.reloadItems();
    }

    // If its already loading then the caller just needs to be informed
    // of when it has finished loading.
    if (this._isLoading) {
      var defer = $q.defer();
      this._extraLoadDefers.push(defer);
      return defer.promise;
    }

    var self = this;
    this._isLoading = true;
    return this._batchLoadItems(this._items, function(item) {
      item.$selected = false;
      self._updateMetadata(item, METADATA_ACTIONS.CREATE);
      self._processItem(item);
    }).then(
      function() {
        self._loaded = true;
        self._isLoading = false;
        self.processActions();
        self._resolveDefers(self._extraLoadDefers, self._items);
        self._extraLoadDefers = [];
        return self._items;
      },
      function(error) {
        self._rejectDefers(self._extraLoadDefers, error);
        self._extraLoadDefers = [];
        return $q.reject(error);
      }
    );
  };

  // Reload the items list.
  Manager.prototype.reloadItems = function() {
    // If the items have not been loaded then, we need to
    // load the initial list.
    if (!this._loaded) {
      return this.loadItems();
    }

    // If its already reloading then the caller just needs to be
    // informed of when it has refinished loading.
    if (this._isLoading) {
      var defer = $q.defer();
      this._extraReloadDefers.push(defer);
      return defer.promise;
    }

    // Updates the items list with the reloaded items.
    var self = this;
    function updateItems(items) {
      // Iterate in reverse so we can remove items inline, without
      // having to adjust the index.
      var i = self._items.length;
      while (i--) {
        var item = self._items[i];
        var updatedIdx = self._getIndexOfItem(items, item[self._pk]);
        if (updatedIdx === -1) {
          self._updateMetadata(item, METADATA_ACTIONS.DELETE);
          self._items.splice(i, 1);
          self._removeItemByIdFromArray(self._selectedItems, item[self._pk]);
        } else {
          var updatedItem = items[updatedIdx];
          self._updateMetadata(updatedItem, METADATA_ACTIONS.UPDATE);
          updatedItem.$selected = item.$selected;
          angular.copy(items[updatedIdx], item);
          items.splice(updatedIdx, 1);
        }
      }

      // The remain items in items array are the new items.
      angular.forEach(items, function(item) {
        self._items.push(item);
        self._processItem(item);
      });
    }

    // The reload action loads all of the items into this list
    // instead of the items list. This list will then be used to
    // update the items list.
    var currentItems = [];

    // Start the reload process and once complete call updateItems.
    self._isLoading = true;
    return this._batchLoadItems(currentItems).then(
      function(items) {
        updateItems(items);
        self._isLoading = false;
        self.processActions();

        // Set the activeItem again so the region knows that its
        // the active item.
        if (angular.isObject(self._activeItem)) {
          self.setActiveItem(self._activeItem[self._pk]);
        }

        self._resolveDefers(self._extraReloadDefers, self._items);
        self._extraReloadDefers = [];
        return self._items;
      },
      function(error) {
        self._rejectDefers(self._extraReloadDefers, error);
        self._extraReloadDefers = [];
        return $q.reject(error);
      }
    );
  };

  // Enables auto reloading of the item list on connection to region.
  Manager.prototype.enableAutoReload = function() {
    if (!this._autoReload) {
      this._autoReload = true;
      var self = this;
      this._reloadFunc = function() {
        self.reloadItems();
      };
      RegionConnection.registerHandler("open", this._reloadFunc);
    }
  };

  // Disable auto reloading of the item list on connection to region.
  Manager.prototype.disableAutoReload = function() {
    if (this._autoReload) {
      RegionConnection.unregisterHandler("open", this._reloadFunc);
      this._reloadFunc = null;
      this._autoReload = false;
    }
  };

  // True when the initial item list has finished loading.
  Manager.prototype.isLoaded = function() {
    return this._loaded;
  };

  // True when the item list is currently being loaded or reloaded.
  Manager.prototype.isLoading = function() {
    return this._isLoading;
  };

  // Allow for extra processing of items as they are added or updated.
  Manager.prototype._processItem = function(item) {};

  // Replace item in the items and selectedItems list.
  Manager.prototype._replaceItem = function(item) {
    this._updateMetadata(item, METADATA_ACTIONS.UPDATE);
    this._replaceItemInArray(this._items, item);
  };

  // Remove item in the items and selectedItems list.
  Manager.prototype._removeItem = function(pk_value) {
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx >= 0) {
      this._updateMetadata(this._items[idx], METADATA_ACTIONS.DELETE);
    }
    this._removeItemByIdFromArray(this._items, pk_value);
    this._removeItemByIdFromArray(this._selectedItems, pk_value);
  };

  // Get the item from the list. Does not make a get request to the
  // region to load more data.
  Manager.prototype.getItemFromList = function(pk_value) {
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx >= 0) {
      return this._items[idx];
    } else {
      return null;
    }
  };

  // Get the item from the region.
  Manager.prototype.getItem = function(pk_value) {
    var self = this;
    var method = this._handler + ".get";
    var params = {};
    params[this._pk] = pk_value;
    return RegionConnection.callMethod(method, params).then(function(item) {
      self._replaceItem(item);
      return item;
    });
  };

  // Send the create information to the region.
  Manager.prototype.createItem = function(item) {
    var self = this;
    var method = this._handler + ".create";
    item = angular.copy(item);
    delete item.$selected;
    return RegionConnection.callMethod(method, item).then(function(item) {
      self._replaceItem(item);
      return item;
    });
  };

  // Send the update information to the region.
  Manager.prototype.updateItem = function(item) {
    var self = this;
    var method = this._handler + ".update";
    item = angular.copy(item);
    delete item.$selected;
    return RegionConnection.callMethod(method, item).then(function(item) {
      self._replaceItem(item);
      return item;
    });
  };

  // Send the delete call for item to the region.
  Manager.prototype.deleteItem = function(item) {
    var self = this;
    var method = this._handler + ".delete";
    var params = {};
    params[this._pk] = item[this._pk];
    return RegionConnection.callMethod(method, params).then(function() {
      self._removeItem(item[self._pk]);
    });
  };

  // Return the active item.
  Manager.prototype.getActiveItem = function() {
    return this._activeItem;
  };

  // Set the active item.
  Manager.prototype.setActiveItem = function(pk_value) {
    if (!this._loaded) {
      throw new Error("Cannot set active item unless the manager is loaded.");
    }
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx === -1) {
      this._activeItem = null;
      // Item with pk_value does not exists. Reject the returned
      // deferred.
      var defer = $q.defer();
      $timeout(function() {
        defer.reject("No item with pk: " + pk_value);
      });
      return defer.promise;
    } else {
      this._activeItem = this._items[idx];
      // Data that is loaded from the list call is limited and
      // doesn't contain all of the needed data for an activeItem.
      // Call set_active on the handler for the region to know
      // this item needs all information when updated.
      var self = this;
      var method = this._handler + ".set_active";
      var params = {};
      params[this._pk] = pk_value;
      return RegionConnection.callMethod(method, params).then(function(item) {
        self._replaceItem(item);
        return self._activeItem;
      });
    }
  };

  // Clears the active item.
  Manager.prototype.clearActiveItem = function() {
    this._activeItem = null;
  };

  // True when the item list is stable and not being loaded or reloaded.
  Manager.prototype.canProcessActions = function() {
    return !this._isLoading;
  };

  // Handle notify from RegionConnection about an item.
  Manager.prototype.onNotify = function(action, data) {
    // Place the notification in the action queue.
    this._actionQueue.push({
      action: action,
      data: data
    });
    // Processing incoming actions is enabled. Otherwise they
    // will be queued until processActions is called.
    if (this.canProcessActions()) {
      $rootScope.$apply(this.processActions());
    }
  };

  // Process all actions to keep the item information up-to-date.
  Manager.prototype.processActions = function() {
    while (this._actionQueue.length > 0) {
      var action = this._actionQueue.shift();
      if (action.action === "create") {
        // Check that the received data doesn't already exists
        // in the _items list. If it does then this is actually
        // an update action not a create action.
        var idx = this._getIndexOfItem(this._items, action.data[this._pk]);
        if (idx >= 0) {
          // Actually this is an update action not a create
          // action. So replace the item instead of adding it.
          this._replaceItem(action.data);
        } else {
          action.data.$selected = false;
          this._updateMetadata(action.data, METADATA_ACTIONS.CREATE);
          this._items.push(action.data);
        }
        this._processItem(action.data);
      } else if (action.action === "update") {
        this._replaceItem(action.data);
        this._processItem(action.data);
      } else if (action.action === "delete") {
        this._removeItem(action.data);
      }
    }
  };

  // Return list of selected items.
  Manager.prototype.getSelectedItems = function() {
    return this._selectedItems;
  };

  // Mark the given item as selected.
  Manager.prototype.selectItem = function(pk_value) {
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx === -1) {
      // eslint-disable-next-line no-console
      console.log(
        "WARN: selection of " +
          this._handler +
          "(" +
          pk_value +
          ") failed because its missing in the items list."
      );
      return;
    }

    var item = this._items[idx];
    item.$selected = true;

    idx = this._selectedItems.indexOf(item);
    if (idx === -1) {
      this._selectedItems.push(item);
    }
  };

  // Mark the given item as unselected.
  Manager.prototype.unselectItem = function(pk_value) {
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx === -1) {
      // eslint-disable-next-line no-console
      console.log(
        "WARN: de-selection of " +
          this._handler +
          "(" +
          pk_value +
          ") failed because its missing in the " +
          "nodes list."
      );
      return;
    }

    var item = this._items[idx];
    item.$selected = false;

    idx = this._selectedItems.indexOf(item);
    if (idx >= 0) {
      this._selectedItems.splice(idx, 1);
    }
  };

  // Determine if a item is selected.
  Manager.prototype.isSelected = function(pk_value) {
    var idx = this._getIndexOfItem(this._items, pk_value);
    if (idx === -1) {
      // eslint-disable-next-line no-console
      console.log(
        "WARN: unable to determine if " +
          this._handler +
          "(" +
          pk_value +
          ") is selected because its missing in the " +
          "nodes list."
      );
      return false;
    }

    return this._items[idx].$selected === true;
  };

  // Return the metadata object value from `metadatas` matching `name`.
  Manager.prototype._getMetadataValue = function(metadatas, name) {
    var i;
    for (i = 0; i < metadatas.length; i++) {
      if (metadatas[i].name === name) {
        return metadatas[i];
      }
    }
    return null;
  };

  // Add new value to metadatas if it doesn't exists or increment the
  // count if it already does.
  Manager.prototype._addMetadataValue = function(metadatas, value) {
    var metadata = this._getMetadataValue(metadatas, value);
    if (metadata) {
      metadata.count += 1;
    } else {
      metadata = {
        name: value,
        count: 1
      };
      metadatas.push(metadata);
    }
  };

  // Remove value from metadatas.
  Manager.prototype._removeMetadataValue = function(metadatas, value) {
    var metadata = this._getMetadataValue(metadatas, value);
    if (metadata) {
      metadata.count -= 1;
      if (metadata.count <= 0) {
        metadatas.splice(metadatas.indexOf(metadata), 1);
      }
    }
  };

  // Update the metadata entry in `metadatas` for the array value and
  // based on the action.
  Manager.prototype._updateMetadataArrayEntry = function(
    metadatas,
    newValue,
    action,
    oldValue
  ) {
    var self = this;

    if (action === METADATA_ACTIONS.CREATE) {
      angular.forEach(newValue, function(value) {
        // On create ignore empty values.
        if (value === "") {
          return;
        }
        self._addMetadataValue(metadatas, value);
      });
    } else if (action === METADATA_ACTIONS.DELETE) {
      angular.forEach(newValue, function(value) {
        self._removeMetadataValue(metadatas, value);
      });
    } else if (
      action === METADATA_ACTIONS.UPDATE &&
      angular.isDefined(oldValue)
    ) {
      // Any values in added are new on the item, and any values left
      // in oldArray have been removed.
      var added = [];
      var oldArray = angular.copy(oldValue);
      angular.forEach(newValue, function(value) {
        var idx = oldArray.indexOf(value);
        if (idx === -1) {
          // Value not in oldArray so it has been added.
          added.push(value);
        } else {
          // Value already in oldArray so its already tracked.
          oldArray.splice(idx, 1);
        }
      });

      // Add the new values.
      angular.forEach(added, function(value) {
        self._addMetadataValue(metadatas, value);
      });

      // Remove the old values.
      angular.forEach(oldArray, function(value) {
        self._removeMetadataValue(metadatas, value);
      });
    }
  };

  // Update the metadata entry in `metadatas` for the newValue and based
  // on the action. Method does not work with array values, use
  // _updateMetadataArrayEntry for values that are arrays.
  Manager.prototype._updateMetadataValueEntry = function(
    metadatas,
    newValue,
    action,
    oldValue
  ) {
    if (action === METADATA_ACTIONS.CREATE) {
      // On create ignore empty values.
      if (newValue === "") {
        return;
      }
      this._addMetadataValue(metadatas, newValue);
    } else if (action === METADATA_ACTIONS.DELETE) {
      this._removeMetadataValue(metadatas, newValue);
    } else if (
      action === METADATA_ACTIONS.UPDATE &&
      angular.isDefined(oldValue)
    ) {
      if (oldValue !== newValue) {
        if (oldValue !== "") {
          // Decrement the old value
          this._removeMetadataValue(metadatas, oldValue);
        }

        // Increment the new value with the "create"
        // operation.
        this._updateMetadataEntry(
          metadatas,
          newValue,
          METADATA_ACTIONS.CREATE,
          oldValue
        );
      }
    }
  };

  // Update the metadata entry in `metadatas` with the newValue and based
  // on the action. Update action will use the oldValue to remove it from
  // the metadata.
  Manager.prototype._updateMetadataEntry = function(
    metadatas,
    newValue,
    action,
    oldValue
  ) {
    if (angular.isArray(newValue)) {
      this._updateMetadataArrayEntry(metadatas, newValue, action, oldValue);
    } else {
      this._updateMetadataValueEntry(metadatas, newValue, action, oldValue);
    }
  };

  // Return the metadata object.
  Manager.prototype.getMetadata = function() {
    return this._metadata;
  };

  // Update the metadata objects based on the given item and action.
  Manager.prototype._updateMetadata = function(item, action) {
    var self = this;
    var oldItem, idx;
    if (action === METADATA_ACTIONS.UPDATE) {
      // Update actions require the oldItem if it exist in the
      // current item listing.
      idx = this._getIndexOfItem(this._items, item[this._pk]);
      if (idx >= 0) {
        oldItem = this._items[idx];
      }
    }
    angular.forEach(this._metadataAttributes, function(func, attr) {
      if (angular.isUndefined(self._metadata[attr])) {
        self._metadata[attr] = [];
      }
      var newValue, oldValue;
      if (angular.isFunction(func)) {
        newValue = func(item);
        if (angular.isObject(oldItem)) {
          oldValue = func(oldItem);
        }
      } else {
        newValue = item[attr];
        if (angular.isObject(oldItem)) {
          oldValue = oldItem[attr];
        }
      }
      self._updateMetadataEntry(
        self._metadata[attr],
        newValue,
        action,
        oldValue
      );
    });
  };

  // Format maas version number
  Manager.prototype.formatMAASVersionNumber = function() {
    if (MAAS_config.version) {
      var versionWithPoint = MAAS_config.version.split(" ")[0];

      if (versionWithPoint) {
        if (versionWithPoint.split(".")[2] === "0") {
          return (
            versionWithPoint.split(".")[0] +
            "." +
            versionWithPoint.split(".")[1]
          );
        } else {
          return versionWithPoint;
        }
      }
    }
  };

  // Default implementation of getName(): returns the default name for
  // this object, if it exists.
  Manager.prototype.getName = function(obj) {
    if (!angular.isObject(obj)) {
      return;
    }
    if (angular.isString(obj[this._name_field])) {
      return obj[this._name_field];
    }
  };

  return Manager;
}

Manager.$inject = ["$q", "$rootScope", "$timeout", "RegionConnection"];

export default Manager;
