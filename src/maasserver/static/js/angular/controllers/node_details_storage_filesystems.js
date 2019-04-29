/*
 * Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Manage a node's filesystems, including adding special filesystems.
 */

class SpecialFilesystem {
  constructor(fstype = null) {
    this.fstype = fstype;
    this.mountPoint = "";
    this.mountOptions = "";
  }

  isValid() {
    return this.mountPoint.startsWith("/");
  }

  describe() {
    if (!this.fstype) {
      return;
    }
    var parts = [this.fstype];
    // Add the mount point if specified and valid.
    if (this.mountPoint.startsWith("/")) {
      parts.push("at " + this.mountPoint);
    }
    // Filesystem-specific bits.
    switch (this.fstype) {
      case "tmpfs":
        // Extract size=n parameter from mount options. Other
        // options could be added in the future.
        var size = this.mountOptions.match(/\bsize=(\d+)(%?)/);
        if (size !== null) {
          if (size[2] === "%") {
            parts.push("limited to " + size[1] + "% of memory");
          } else {
            parts.push("limited to " + size[1] + " bytes");
          }
        }
        break;
      case "ramfs":
        // This filesystem does not recognise any options. Consider
        // warning about lack of a size limit.
        break;
    }
    return parts.join(" ");
  }
}

/* @ngInject */
export function NodeFilesystemsController($scope) {
  // Which drop-down is currently selected, e.g. "special".
  $scope.dropdown = null;

  // Select the "special" drop-down.
  $scope.addSpecialFilesystem = function() {
    $scope.dropdown = "special";
  };

  // Deselect the "special" drop-down.
  $scope.addSpecialFilesystemFinished = function() {
    if ($scope.dropdown === "special") {
      $scope.dropdown = null;
    }
  };
}

/* @ngInject */
export function NodeAddSpecialFilesystemController($scope, MachinesManager) {
  $scope.machineManager = MachinesManager;
  $scope.specialFilesystemTypes = ["tmpfs", "ramfs"];
  $scope.newFilesystem = {
    system_id: $scope.node.system_id
  };
  $scope.filesystem = new SpecialFilesystem();
  $scope.description = null; // Updated by watch.

  const watches = {
    fstype: "fstype",
    mountPoint: "mount_point",
    mountOptions: "mount_options"
  };

  for (let k in watches) {
    $scope.$watch(
      function() {
        return $scope.newFilesystem.$maasForm.getValue(watches[k]);
      },
      function(result) {
        $scope.filesystem[k] = result;
      }
    );
  }

  $scope.$watch(
    "filesystem",
    function() {
      if ($scope.filesystem) {
        $scope.description = $scope.filesystem.describe();
      }
    },
    true
  );

  $scope.canMount = function() {
    return $scope.filesystem.isValid();
  };

  $scope.cancel = function() {
    $scope.filesystem = new SpecialFilesystem();
    $scope.addSpecialFilesystemFinished();
  };
}
