/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script select directive.
 */

function filterScriptsByParam(scripts, param) {
  return scripts.filter(script => {
    const hasParam = Object.values(script.parameters).filter(value => {
      return value.type === param;
    });
    return hasParam.length > 0;
  });
}

/* @ngInject */
export function maasScriptSelect(ScriptsManager, ManagerHelperService) {
  return {
    restrict: "A",
    require: "ngModel",
    scope: {
      ngModel: "=",
      scriptType: "=",
      setDefaultValues: "=",
      checkTestParameterValues: "="
    },
    templateUrl: "static/partials/add-scripts.html",
    link: ($scope, element) => {
      $scope.allScripts = ScriptsManager.getItems();
      $scope.scripts = [];
      $scope.scriptsWithUrlParam = [];
      $scope.currentScript = {};
      $scope.onParameterChange = $scope.checkTestParameterValues;

      $scope.getScripts = query => {
        $scope.scripts.length = 0;

        angular.forEach($scope.allScripts, script => {
          if (
            script.script_type === $scope.scriptType &&
            script.name.indexOf(query) >= 0
          ) {
            script.tags_string = "";

            angular.forEach(script.tags, tag => {
              if (script.tags_string === "") {
                script.tags_string = "(" + tag;
              } else {
                script.tags_string += ", " + tag;
              }
            });

            if (script.tags_string !== "") {
              script.tags_string += ")";
            }

            $scope.scripts.push(script);
          }
        });
        return {
          data: $scope.scripts
        };
      };

      $scope.onTagAdding = tag => {
        tag.parameters = $scope.setDefaultValues(tag.parameters);
        return tag.id !== undefined;
      };

      $scope.onTagAdded = () => {
        $scope.scriptsWithUrlParam = filterScriptsByParam(
          $scope.ngModel,
          "url"
        );
        $scope.onParameterChange();
        $scope.refocus();
      };

      $scope.onTagRemoved = () => {
        $scope.scriptsWithUrlParam = filterScriptsByParam(
          $scope.ngModel,
          "url"
        );
        $scope.onParameterChange();
        $scope.refocus();
      };

      $scope.refocus = () => {
        var tagsInput = element.find("tags-input");
        var tagsInputScope = tagsInput.isolateScope();
        if (tagsInputScope) {
          tagsInputScope.eventHandlers.input.change("");
          tagsInputScope.eventHandlers.input.focus();
        }
        tagsInput.find("input").focus();
      };

      if (!angular.isArray($scope.ngModel)) {
        $scope.ngModel = [];
      }

      ManagerHelperService.loadManager($scope, ScriptsManager).then(() => {
        $scope.ngModel.length = 0;

        angular.forEach($scope.allScripts, script => {
          if (
            script.script_type === $scope.scriptType &&
            script.for_hardware.length === 0
          ) {
            if ($scope.scriptType === 0) {
              // By default MAAS runs all custom
              // commissioning scripts in addition to all
              // builtin commissioning scripts.
              $scope.ngModel.push(script);
            } else if (
              $scope.scriptType === 2 &&
              script.tags.indexOf("commissioning") >= 0
            ) {
              // By default MAAS runs testing scripts which
              // have been tagged 'commissioning'
              $scope.ngModel.push(script);
            }
          }
        });

        $scope.scriptsWithUrlParam = filterScriptsByParam(
          $scope.ngModel,
          "url"
        );

        $scope.scriptsWithUrlParam.forEach(script => {
          script.parameters = $scope.setDefaultValues(script.parameters);
        });
      });
    }
  };
}
