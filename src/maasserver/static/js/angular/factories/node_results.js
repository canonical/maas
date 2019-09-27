/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS NodeResultsManager Manager
 *
 * Manages all of the NodeResults in the browser. The manager uses the
 * RegionConnection to load the NodeResults, and listen for
 * notification events about NodeResults.
 */

import { HardwareType } from "../enum";

function NodeResultsManagerFactory(RegionConnection, Manager) {
  function NodeResultsManager(node, factory) {
    Manager.call(this);

    this._pk = "id";
    this._handler = "noderesult";
    this._node = node;
    this._factory = factory;

    // Store as an array to preserve order.
    this.commissioning_results = [
      {
        title: null,
        hardware_type: HardwareType.NODE,
        results: {}
      },
      {
        title: "CPU",
        hardware_type: HardwareType.CPU,
        results: {}
      },
      {
        title: "Memory",
        hardware_type: HardwareType.MEMORY,
        results: {}
      },
      {
        title: "Storage",
        hardware_type: HardwareType.STORAGE,
        results: {}
      },
      {
        title: "Network",
        hardware_type: HardwareType.NETWORK,
        results: {}
      }
    ];
    this.testing_results = [
      {
        title: "CPU",
        hardware_type: HardwareType.CPU,
        results: {}
      },
      {
        title: "Memory",
        hardware_type: HardwareType.MEMORY,
        results: {}
      },
      {
        title: "Storage",
        hardware_type: HardwareType.STORAGE,
        results: {}
      },
      {
        title: "Other Results",
        hardware_type: HardwareType.NODE,
        results: {}
      },
      {
        title: "Network",
        hardware_type: HardwareType.NETWORK,
        results: {}
      }
    ];
    this.installation_results = [];

    // Listen for notify events for the ScriptResult object.
    // This is noderesult instead of scriptresult because the
    // class name is NodeResultHandler.
    var self = this;
    RegionConnection.registerNotifier("noderesult", function(action, data) {
      self.onNotify(action, data);
    });
  }

  NodeResultsManager.prototype = new Manager();

  NodeResultsManager.prototype._getStorageSubtext = function(disk) {
    var deviceinfo = "";
    if (disk.model !== "") {
      deviceinfo += "Model: " + disk.model;
    }
    if (disk.serial !== "") {
      if (deviceinfo !== "") {
        deviceinfo += ", ";
      }
      deviceinfo += "Serial: " + disk.serial;
    }
    if (deviceinfo !== "") {
      return "/dev/" + disk.name + " (" + deviceinfo + ")";
    } else {
      return "/dev/" + disk.name;
    }
  };

  NodeResultsManager.prototype._updateObject = function(existing, updated) {
    angular.forEach(updated, function(value, key) {
      if (
        existing[key] !== value &&
        key !== "showing_results" &&
        key !== "showing_history" &&
        key !== "showing_menu" &&
        key !== "$selected"
      ) {
        existing[key] = value;
      }
    });
  };

  NodeResultsManager.prototype._addOrReplace = function(results, result) {
    for (let i = 0; i < results.length; i++) {
      if (results[i].name === result.name) {
        // Object already exists, update fields.
        result.$selected = results[i].$selected;
        result.showing_results = results[i].showing_results;
        result.showing_history = results[i].showing_history;
        result.showing_menu = results[i].showing_menu;
        angular.copy(result, results[i]);
        return;
      }
    }
    // No result with the same name exists, add it to the sorted list.
    for (let i = 0; i < results.length; i++) {
      if (results[i].name > result.name) {
        results.splice(i, 0, result);
        return;
      }
    }
    results.push(result);
  };

  NodeResultsManager.prototype._processItem = function(result) {
    var results;
    result.showing_results = false;
    result.showing_history = false;
    result.showing_menu = false;
    result.result_section = "scripts";

    if (result.result_type === 0) {
      results = this.commissioning_results;
    } else if (result.result_type === 1) {
      // Installation results are not split into hardware types or
      // have subtext labels.
      this._addOrReplace(this.installation_results, result);
      return;
    } else {
      // Store all remaining result types as test results in case
      // another result type is ever added.
      results = this.testing_results;
      result.result_section = "tests";
    }
    // Fallback to storing results in other results incase a new type
    // is added
    var hardware_type_results = results[3];
    for (let i = 0; i < results.length; i++) {
      if (results[i].hardware_type === result.hardware_type) {
        hardware_type_results = results[i].results;
        break;
      }
    }

    if (
      result.hardware_type === HardwareType.STORAGE &&
      result.physical_blockdevice !== null &&
      this._node.disks
    ) {
      // Storage results are split into individual components.
      let disk, subtext;
      // If the storage result is associated with a specific
      // component generate subtext for that component.
      for (let i = 0; i < this._node.disks.length; i++) {
        disk = this._node.disks[i];
        if (disk.id === result.physical_blockdevice) {
          subtext = this._getStorageSubtext(disk);
          if (!angular.isArray(hardware_type_results[subtext])) {
            hardware_type_results[subtext] = [];
          }
          this._addOrReplace(hardware_type_results[subtext], result);
          break;
        }
      }
    } else if (
      result.hardware_type === HardwareType.NETWORK &&
      result.interface &&
      this._node.interfaces
    ) {
      const nic = this._node.interfaces.find(
        item => item.id === result.interface
      );

      let resultTitle = "";

      if (nic) {
        resultTitle = `${nic.name} (${nic.mac_address})`;

        if (!angular.isArray(hardware_type_results[resultTitle])) {
          hardware_type_results[resultTitle] = [];
        }

        this._addOrReplace(hardware_type_results[resultTitle], result);
      }
    } else {
      // Other hardware types are not split into individual
      // components.
      if (!angular.isArray(hardware_type_results[null])) {
        hardware_type_results[null] = [];
      }
      this._addOrReplace(hardware_type_results[null], result);
    }
  };

  NodeResultsManager.prototype._removeItem = function(result) {
    var idx = this._getIndexOfItem(this._items, result.id);
    if (idx >= 0) {
      this._updateMetadata(this._items[idx], "delete");
    }
    this._removeItemByIdFromArray(this._items, result.id);
    this._removeItemByIdFromArray(this._selectedItems, result.id);

    var self = this;
    angular.forEach(this.commissioning_results, function(hw_type) {
      angular.forEach(hw_type.results, function(results, subtext) {
        self._removeItemByIdFromArray(results, result.id);
        if (results.length === 0) {
          delete hw_type.results[subtext];
        }
      });
    });
    angular.forEach(this.testing_results, function(hw_type) {
      angular.forEach(hw_type.results, function(results, subtext) {
        self._removeItemByIdFromArray(results, result.id);
        if (results.length === 0) {
          delete hw_type.results[subtext];
        }
      });
    });
    this._removeItemByIdFromArray(this.installation_results, result.id);
  };

  // Return the list of ScriptResults for the given node when retrieving
  // the initial list.
  NodeResultsManager.prototype._initBatchLoadParameters = function() {
    var ret = {
      system_id: this._node.system_id
    };
    // Limit the results returned to what can be viewed.
    if (this._area === "summary") {
      ret.has_surfaced = true;
      ret.result_type = 2;
    } else if (this._area === "testing") {
      ret.result_type = 2;
    } else if (this._area === "commissioning") {
      ret.result_type = 0;
    } else if (this._area === "logs") {
      ret.result_type = 1;
    }
    return ret;
  };

  // Destroys itself. Removes self from the NodeResultsManagerFactory.
  NodeResultsManager.prototype.destroy = function() {
    this._factory.destroyManager(this);

    // If this manager has ever loaded then the region is sending
    // results from this node. Tell the RegionConnection to stop.
    if (this.isLoaded()) {
      var method = this._handler + ".clear";
      RegionConnection.callMethod(method, {
        system_id: this._node.system_id
      });
    }
  };

  // Get result data.
  NodeResultsManager.prototype.get_result_data = function(
    script_id,
    data_type
  ) {
    var method = this._handler + ".get_result_data";
    var params = {
      id: script_id,
      data_type: data_type
    };
    return RegionConnection.callMethod(method, params);
  };

  // Get historic data.
  NodeResultsManager.prototype.get_history = function(script_id) {
    var method = this._handler + ".get_history";
    var params = {
      id: script_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Factory that holds all created NodeResultsManagers.
  function NodeResultsManagerFactory() {
    // Holds a list of all NodeResultsManagers that have been created.
    this._managers = [];
  }

  // Gets the NodeResultsManager for the nodes with node_system_id.
  NodeResultsManagerFactory.prototype._getManager = function(node) {
    for (let i = 0; i < this._managers.length; i++) {
      if (this._managers[i]._node.system_id === node.system_id) {
        return this._managers[i];
      }
    }
    return null;
  };

  // Gets the NodeResultsManager for the nodes system_id. Creates a new
  // manager if one does not exist.
  NodeResultsManagerFactory.prototype.getManager = function(node, area) {
    var manager = this._getManager(node);
    if (!angular.isObject(manager)) {
      // Not created so create it.
      manager = new NodeResultsManager(node, this);
      this._managers.push(manager);
    }
    manager._area = area;
    if (area === "commissioning") {
      manager.results = manager.commissioning_results;
    } else if (area === "logs") {
      manager.results = manager.installation_results;
    } else {
      manager.results = manager.testing_results;
    }
    return manager;
  };

  // Destroy the NodeResultsManager.
  NodeResultsManagerFactory.prototype.destroyManager = function(manager) {
    var idx = this._managers.indexOf(manager);
    if (idx >= 0) {
      this._managers.splice(idx, 1);
    }
  };

  return new NodeResultsManagerFactory();
}

NodeResultsManagerFactory.$inject = ["RegionConnection", "Manager"];

export default NodeResultsManagerFactory;
