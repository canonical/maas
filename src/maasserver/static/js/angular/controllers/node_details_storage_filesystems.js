/*
 * Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Manage a node's filesystems, including adding special filesystems.
 */

(function() {

    function SpecialFilesystem() {
        this.fstype = "tmpfs";
        this.mountPoint = "";
        this.mountOptions = "";
    }

    SpecialFilesystem.prototype.isValid = function() {
        return this.mountPoint.startsWith("/");
    };

    SpecialFilesystem.prototype.describe = function() {
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
    };

    function NodeFilesystemsController($scope) {

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

    function NodeAddSpecialFilesystemController($scope, MachinesManager) {

        $scope.filesystem = new SpecialFilesystem();
        $scope.description = null;  // Updated by watch.

        $scope.$watch("filesystem", function(filesystem) {
            $scope.description = filesystem.describe();
        }, true);

        $scope.canMount = function() {
            return $scope.filesystem.isValid();
        };

        $scope.mount = function() {
            MachinesManager.mountSpecialFilesystem(
                $scope.node, $scope.filesystem.fstype,
                $scope.filesystem.mountPoint,
                $scope.filesystem.mountOptions);
            $scope.addSpecialFilesystemFinished();
        };

        $scope.cancel = function() {
            $scope.filesystem = new SpecialFilesystem();
            $scope.addSpecialFilesystemFinished();
        };
    }

    angular.module("MAAS").controller(
        "NodeFilesystemsController", [
            "$scope", NodeFilesystemsController
        ]);

    angular.module("MAAS").controller(
        "NodeAddSpecialFilesystemController", [
            "$scope", "MachinesManager",
            NodeAddSpecialFilesystemController
        ]);

}());
