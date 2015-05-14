/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * OS/Release select directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the os-select.html into the template cache.
    $templateCache.put('directive/templates/os-select.html', [
        '<select name="os" data-ng-model="ngModel.osystem" ',
            'data-ng-change="selectedOSChanged()" ',
            'data-ng-options="',
            'os[0] as os[1] for os in maasOsSelect.osystems">',
        '</select>',
        '<select name="release" data-ng-model="ngModel.release" ',
            'data-ng-options="',
            'release[0] as release[1] for release in releases">',
        '</select>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasOsSelect', function() {
    return {
        restrict: "A",
        require: "ngModel",
        scope: {
            maasOsSelect: '=',
            ngModel: '='
        },
        templateUrl: 'directive/templates/os-select.html',
        controller: function($scope) {

            // Return only the selectable releases based on the selected os.
            function getSelectableReleases() {
                if(angular.isObject($scope.maasOsSelect) &&
                    angular.isArray($scope.maasOsSelect.releases)) {
                    var i, allChoices = $scope.maasOsSelect.releases;
                    var choice, choices = [];
                    for(i = 0; i < allChoices.length; i++) {
                        choice = allChoices[i];
                        if(choice[0].indexOf($scope.ngModel.osystem) > -1) {
                            choices.push(choice);
                        }
                    }
                    return choices;
                }
                return [];
            }

            // Returns the defaultValue if its in the choices array. Otherwise
            // it returns the weighted choice if present, followed by the
            // first choice.
            function getDefaultOrFirst(array, defaultValue, weightValue) {
                var i, first, weightedPresent = false;
                for(i = 0; i < array.length; i++) {
                    if(angular.isUndefined(first)) {
                        first = array[i][0];
                    }
                    if(array[i][0] === defaultValue) {
                        return defaultValue;
                    }
                    if(angular.isString(weightValue) &&
                        array[i][0] === weightValue) {
                        weightedPresent = true;
                    }
                }
                if(weightedPresent) {
                    return weightValue;
                }
                if(angular.isUndefined(first)) {
                    return null;
                }
                return first;
            }

            // Sets the default selected values for the ngModel. Only sets the
            // values once the maasOsSelect is populated. Sets the selected
            // osystem to default_osystem if present, followed by 'ubuntu' if
            // present, followed by the first available. Sets the selected
            // release to the default_release if present, followed by the first
            // available.
            function setDefault() {
                // Do nothing if model is already set.
                if(angular.isString($scope.ngModel.osystem) &&
                    angular.isString($scope.ngModel.release)) {
                    return;
                }
                // Do nothing if the default is not set.
                if(angular.isUndefined($scope.maasOsSelect.default_osystem) ||
                    angular.isUndefined($scope.maasOsSelect.default_release)) {
                    return;
                }

                // Set the intial defaults.
                $scope.ngModel.osystem = getDefaultOrFirst(
                    $scope.maasOsSelect.osystems,
                    $scope.maasOsSelect.default_osystem, "ubuntu");
                $scope.releases = getSelectableReleases();
                $scope.ngModel.release = getDefaultOrFirst(
                    $scope.releases,
                    $scope.ngModel.osystem + "/" +
                    $scope.maasOsSelect.default_release);
            }

            // Defaults
            if(!angular.isObject($scope.ngModel)) {
                $scope.ngModel = {
                    osystem: null,
                    release: null
                };
            }
            $scope.releases = getSelectableReleases();

            // Add the reset function to ngModel, allowing users to call
            // this function to reset the defauls.
            $scope.ngModel.$reset = function() {
                $scope.ngModel.osystem = null;
                $scope.ngModel.release = null;
                setDefault();
            };

            // If the available os change update the available releases and
            // set the default.
            $scope.$watch("maasOsSelect.releases", function() {
                $scope.releases = getSelectableReleases();
                setDefault();
            });

            // Updates the default and selectable releases.
            $scope.selectedOSChanged = function() {
                $scope.releases = getSelectableReleases();
                $scope.ngModel.release = null;
                if($scope.releases.length > 0) {
                    $scope.ngModel.release = $scope.releases[0][0];
                }
            };
        }
    };
});
