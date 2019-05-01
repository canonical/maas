/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * SSH keys directive.
 */

/* @ngInject */
function maasSshKeys($sce, SSHKeysManager, ManagerHelperService, JSONService) {
  return {
    restrict: "E",
    scope: {},
    templateUrl: "static/partials/ssh-keys.html?v=" + MAAS_config.files_version,
    controller: SSHKeysController
  };

  /* @ngInject */
  function SSHKeysController($scope) {
    $scope.loading = true;
    $scope.keys = SSHKeysManager.getItems();
    $scope.groupedKeys = [];
    $scope.add = {
      source: "lp",
      authId: "",
      key: "",
      error: null,
      saving: false
    };
    $scope.sourceTitles = {
      lp: "Launchpad",
      gh: "Github",
      upload: "Upload"
    };
    $scope.openRow = null;
    $scope.rowMode = null;

    // Expose trustAsHtml on the scope for the view to use.
    $scope.trustAsHtml = $sce.trustAsHtml;

    // Open a row.
    $scope.open = function(obj, mode) {
      $scope.openRow = obj.id;
      $scope.rowMode = mode;
    };

    // Close the open row.
    $scope.close = function() {
      $scope.openRow = null;
    };

    // Returns true if the key can be imported.
    $scope.canImportKeys = function() {
      if ($scope.add.saving) {
        return false;
      } else if ($scope.add.source === "lp" || $scope.add.source === "gh") {
        return $scope.add.authId.length > 0;
      } else {
        return $scope.add.key.length > 0;
      }
    };

    // Called to import the key.
    $scope.importKeys = function() {
      if (!$scope.canImportKeys()) {
        return;
      }
      $scope.add.error = null;
      $scope.add.saving = true;
      if ($scope.add.source === "lp" || $scope.add.source === "gh") {
        SSHKeysManager.importKeys({
          protocol: $scope.add.source,
          auth_id: $scope.add.authId
        }).then(
          function() {
            $scope.open(
              {
                id: `${$scope.add.source}/${$scope.add.authId}`
              },
              "view"
            );
            $scope.add.saving = false;
            $scope.add.source = "lp";
            $scope.add.authId = "";
            $scope.add.key = "";
          },
          function(error) {
            $scope.add.saving = false;
            var errorJson = JSONService.tryParse(error);
            if (angular.isObject(errorJson)) {
              if (angular.isArray(errorJson.__all__)) {
                $scope.add.error = errorJson.__all__[0];
              } else {
                $scope.add.error = error;
              }
            } else {
              $scope.add.error = error;
            }
          }
        );
      } else {
        SSHKeysManager.createItem({
          key: $scope.add.key
        }).then(
          function() {
            $scope.add.saving = false;
            $scope.add.source = "lp";
            $scope.add.authId = "";
            $scope.add.key = "";
          },
          function(error) {
            $scope.add.saving = false;
            var errorJson = JSONService.tryParse(error);
            if (angular.isObject(errorJson)) {
              if (angular.isArray(errorJson.key)) {
                $scope.add.error = errorJson.key[0];
              } else if (angular.isArray(errorJson.__all__)) {
                $scope.add.error = errorJson.__all__[0];
              } else {
                $scope.add.error = error;
              }
            } else {
              $scope.add.error = error;
            }
          }
        );
      }
    };

    // Called to delete the selected group of keys.
    $scope.confirmDelete = function(obj) {
      angular.forEach(obj.keys, function(key) {
        SSHKeysManager.deleteItem(key);
      });
    };

    // Updates the groupedKeys that is used to render the table.
    $scope.$watchCollection("keys", function() {
      $scope.groupedKeys = [];
      var keyMap = {};
      angular.forEach($scope.keys, function(key) {
        var groupObj,
          keysource = key.keysource;
        if (angular.isObject(keysource)) {
          var keysourceKey = keysource.protocol + "/" + keysource.auth_id;
          groupObj = keyMap[keysourceKey];
          if (angular.isObject(groupObj)) {
            groupObj.keys.push(key);
          } else {
            groupObj = {
              id: keysourceKey,
              source: keysource.protocol,
              authId: keysource.auth_id,
              keys: [key]
            };
            keyMap[keysourceKey] = groupObj;
            $scope.groupedKeys.push(groupObj);
          }
        } else {
          groupObj = {
            id: "upload/" + key.id,
            source: "upload",
            authId: "",
            keys: [key]
          };
          $scope.groupedKeys.push(groupObj);
        }
      });
    });

    ManagerHelperService.loadManager($scope, SSHKeysManager).then(function() {
      $scope.loading = false;
    });
  }
}

export default maasSshKeys;
