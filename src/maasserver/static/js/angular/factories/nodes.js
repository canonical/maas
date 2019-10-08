/* Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes Manager
 *
 * Manages all of the nodes in the browser. This manager is used for the
 * machine and controller listing and view pages (as machines and controllers
 * are both Nodes).  The manager uses the RegionConnection to load the nodes,
 * update the nodes, and listen for notification events about nodes.
 */

function NodesManager(RegionConnection, Manager, KVMDeployOSBlacklist, $log) {
  function NodesManager() {
    Manager.call(this);
  }

  NodesManager.prototype = new Manager();

  // Create a node.
  NodesManager.prototype.create = function(node) {
    // We don't add the item to the list because a NOTIFY event will
    // add the node to the list. Adding it here will cause angular
    // to complain because the same object exist in the list.
    return RegionConnection.callMethod(this._handler + ".create", node);
  };

  // Perform the action on the node.
  NodesManager.prototype.performAction = function(node, action, extra) {
    if (!angular.isObject(extra)) {
      extra = {};
    }

    return RegionConnection.callMethod(this._handler + ".action", {
      system_id: node.system_id,
      action: action,
      extra: extra
    });
  };

  // Check the power state for the node.
  NodesManager.prototype.checkPowerState = function(node) {
    return RegionConnection.callMethod(this._handler + ".check_power", {
      system_id: node.system_id
    }).then(
      function(state) {
        node.power_state = state;
        return state;
      },
      function(error) {
        node.power_state = "error";

        // Already been logged server side, but log it client
        // side so if they really care they can see why.
        $log.error(error);

        // Return the state as error to the remaining callbacks.
        return "error";
      }
    );
  };

  // Create the physical interface on the node.
  NodesManager.prototype.createPhysicalInterface = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(
      this._handler + ".create_physical",
      params
    );
  };

  // Create the VLAN interface on the node.
  NodesManager.prototype.createVLANInterface = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(this._handler + ".create_vlan", params);
  };

  // Create the bond interface on the node.
  NodesManager.prototype.createBondInterface = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(this._handler + ".create_bond", params);
  };

  // Create the bridge interface on the node.
  NodesManager.prototype.createBridgeInterface = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(
      this._handler + ".create_bridge",
      params
    );
  };

  // Update the interface for the node.
  NodesManager.prototype.updateInterface = function(
    node,
    interface_id,
    params
  ) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    params.interface_id = interface_id;
    return RegionConnection.callMethod(
      this._handler + ".update_interface",
      params
    );
  };

  // Update an interface from a maas-obj-form.
  NodesManager.prototype.updateInterfaceForm = function(params) {
    return RegionConnection.callMethod(
      this._handler + ".update_interface",
      params
    );
  };

  // Delete the interface for the node.
  NodesManager.prototype.deleteInterface = function(node, interface_id) {
    var params = {
      system_id: node.system_id,
      interface_id: interface_id
    };
    return RegionConnection.callMethod(
      this._handler + ".delete_interface",
      params
    );
  };

  // Create or update the link to the subnet for the interface.
  NodesManager.prototype.linkSubnet = function(node, interface_id, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    params.interface_id = interface_id;
    return RegionConnection.callMethod(this._handler + ".link_subnet", params);
  };

  // Remove the link to the subnet for the interface.
  NodesManager.prototype.unlinkSubnet = function(node, interface_id, link_id) {
    var params = {
      system_id: node.system_id,
      interface_id: interface_id,
      link_id: link_id
    };
    return RegionConnection.callMethod(
      this._handler + ".unlink_subnet",
      params
    );
  };

  // Send the update information to the region.
  NodesManager.prototype.updateFilesystem = function(
    node,
    block_id,
    partition_id,
    fstype,
    mount_point,
    mount_options,
    tags
  ) {
    var method = this._handler + ".update_filesystem";
    var params = {
      system_id: node.system_id,
      block_id: block_id,
      partition_id: partition_id,
      fstype: fstype,
      mount_point: mount_point,
      mount_options: mount_options,
      tags: tags
    };
    return RegionConnection.callMethod(method, params);
  };

  // Delete the disk.
  NodesManager.prototype.deleteDisk = function(node, block_id) {
    var method = this._handler + ".delete_disk";
    var params = {
      system_id: node.system_id,
      block_id: block_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Delete the partition.
  NodesManager.prototype.deletePartition = function(node, partition_id) {
    var method = this._handler + ".delete_partition";
    var params = {
      system_id: node.system_id,
      partition_id: partition_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Delete the disk or partition.
  NodesManager.prototype.deleteVolumeGroup = function(node, volume_group_id) {
    var method = this._handler + ".delete_volume_group";
    var params = {
      system_id: node.system_id,
      volume_group_id: volume_group_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Delete a cache set.
  NodesManager.prototype.deleteCacheSet = function(node, cache_set_id) {
    var method = this._handler + ".delete_cache_set";
    var params = {
      system_id: node.system_id,
      cache_set_id: cache_set_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Delete a filesystem.
  NodesManager.prototype.deleteFilesystem = function(
    node,
    blockdevice_id,
    partition_id,
    filesystem_id
  ) {
    var method = this._handler + ".delete_filesystem";
    var params = {
      system_id: node.system_id,
      blockdevice_id: blockdevice_id,
      partition_id: partition_id,
      filesystem_id: filesystem_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Create a new partition.
  NodesManager.prototype.createPartition = function(partition) {
    let params;
    if (angular.isObject(partition["params"])) {
      params = partition["params"];
    } else {
      params = {};
    }
    var method = this._handler + ".create_partition";
    params.system_id = partition["system_id"];
    params.block_id = partition["block_id"];
    params.partition_size = partition["partition_size"];

    return RegionConnection.callMethod(method, params);
  };

  // Create a new cache set.
  NodesManager.prototype.createCacheSet = function(
    node,
    block_id,
    partition_id
  ) {
    var method = this._handler + ".create_cache_set";
    var params = {
      system_id: node.system_id,
      block_id: block_id,
      partition_id: partition_id
    };
    return RegionConnection.callMethod(method, params);
  };

  // Create a new bcache device.
  NodesManager.prototype.createBcache = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(
      this._handler + ".create_bcache",
      params
    );
  };

  // Create a new RAID device.
  NodesManager.prototype.createRAID = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(this._handler + ".create_raid", params);
  };

  // Create a new volume group.
  NodesManager.prototype.createVolumeGroup = function(node, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    return RegionConnection.callMethod(
      this._handler + ".create_volume_group",
      params
    );
  };

  // Create a new logical volume.
  NodesManager.prototype.createLogicalVolume = function(
    node,
    volume_group_id,
    name,
    size,
    params
  ) {
    if (!angular.isObject(params)) {
      params = {};
    }
    var method = this._handler + ".create_logical_volume";
    params.system_id = node.system_id;
    params.volume_group_id = volume_group_id;
    params.name = name;
    params.size = size;
    return RegionConnection.callMethod(method, params);
  };

  // Update a disk.
  NodesManager.prototype.updateDisk = function(node, block_id, params) {
    if (!angular.isObject(params)) {
      params = {};
    }
    params.system_id = node.system_id;
    params.block_id = block_id;
    return RegionConnection.callMethod(this._handler + ".update_disk", params);
  };

  // Set disk as the boot disk.
  NodesManager.prototype.setBootDisk = function(node, block_id) {
    var params = {
      system_id: node.system_id,
      block_id: block_id
    };
    return RegionConnection.callMethod(
      this._handler + ".set_boot_disk",
      params
    );
  };

  NodesManager.prototype.getSummaryXML = function(node) {
    return RegionConnection.callMethod(this._handler + ".get_summary_xml", {
      system_id: node.system_id
    });
  };

  NodesManager.prototype.getSummaryYAML = function(node) {
    return RegionConnection.callMethod(this._handler + ".get_summary_yaml", {
      system_id: node.system_id
    });
  };

  NodesManager.prototype.isModernUbuntu = function(osSelection) {
    if (!osSelection) {
      return false;
    }

    if (osSelection.osystem !== "ubuntu") {
      return false;
    }

    if (KVMDeployOSBlacklist.includes(osSelection.release)) {
      return false;
    }

    return true;
  };

  NodesManager.prototype.suppressTests = function(node, scripts) {
    return RegionConnection.callMethod(
      this._handler + ".set_script_result_suppressed",
      {
        system_id: node.system_id,
        script_result_ids: scripts.map(script => script.id)
      }
    );
  };

  NodesManager.prototype.unsuppressTests = function(node, scripts) {
    return RegionConnection.callMethod(
      this._handler + ".set_script_result_unsuppressed",
      {
        system_id: node.system_id,
        script_result_ids: scripts.map(script => script.id)
      }
    );
  };

  NodesManager.prototype.getLatestFailedTests = function(nodes) {
    return RegionConnection.callMethod(
      this._handler + ".get_latest_failed_testing_script_results",
      {
        system_ids: nodes.map(node => node.system_id)
      }
    ).then(results => results, error => error);
  };

  return NodesManager;
}

NodesManager.$inject = [
  "RegionConnection",
  "Manager",
  "KVMDeployOSBlacklist",
  "$log"
];

export default NodesManager;
